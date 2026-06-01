#!/usr/bin/env python3
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
"""CLI eval runner for scone-bench.

Spins up one Docker container per (problem, iteration), drives the model via the
Anthropic/OpenAI/OpenRouter API against the container's MCP server, and writes a
transcript JSON per attempt.
"""

import argparse
import asyncio
import json
import os
import random
import re
import shlex
import socket
from datetime import UTC, datetime
from pathlib import Path

from client import MCPClient
from utils import stream_agentic_response


async def _execute_problem(
    problem_id: str,
    image: str,
    startup_command: str,
    model: str,
    max_tokens: int,
    transcript_path: str,
    retry_config: dict | None,
    timeout: int,  # noqa: ASYNC109
    thinking_budget: int,
):
    """Launch a fresh container for one problem attempt and return the SSE stream."""
    docker_cmd = ["docker", "run", "-d", "-i"]

    # Publish anvil's 8545 on an ephemeral host port so the model's `forge`/`cast`
    # inside the container don't collide across parallel containers.
    if "scone-bench" in image:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            host_port = s.getsockname()[1]
        docker_cmd.extend(["-p", f"{host_port}:8545"])

    # Forward the env vars the server needs (RPC URLs, API keys, optional cache).
    for k in os.environ:
        if k.startswith("SCONE_") or k in {
            "ETHERSCAN_API_KEY",
            "COINGECKO_API_KEY",
            "COVALENT_API_KEY",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
        }:
            docker_cmd.extend(["-e", k])

    # `image` and `startup_command` come from the metadata JSON. Reject anything
    # that could be parsed as a docker flag, and use `--` so docker stops option
    # parsing before the positional image arg.
    if not re.fullmatch(r"[A-Za-z0-9][\w./:-]*", image):
        raise ValueError(f"refusing image {image!r}: not a plain image ref")
    cmd_tokens = shlex.split(startup_command)
    if any(t.startswith("-") for t in cmd_tokens[:1]):
        raise ValueError(f"refusing startup_command {startup_command!r}: leading flag")
    docker_cmd.extend(["--", image, *cmd_tokens])

    process = await asyncio.create_subprocess_exec(
        *docker_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"Failed to create container: {stderr.decode()}")

    container_id = stdout.decode().strip()

    mcp_client = MCPClient(problem_id, container_id, model)

    return stream_agentic_response(
        mcp_client=mcp_client,
        model=model,
        max_tokens=max_tokens,
        problem_id=problem_id,
        container_id=container_id,
        transcript_path=transcript_path,
        retry_config=retry_config,
        thinking_budget=thinking_budget,
    )


async def run_evaluation(
    max_tokens: int,
    times_per_problem: int,
    problems_metadata_path: str,
    parallel_requests: int,
    transcript_dir: str,
    model: str = "claude-sonnet-4-5",
    timeout: int = 10,  # noqa: ASYNC109
    retry_config: dict | None = None,
    thinking_budget: int = 10000,
) -> None:
    """Run the evaluation with bounded parallelism."""
    with open(problems_metadata_path) as f:
        metadata = json.load(f)["problem_set"]

    problems = metadata.get("problems", [])
    if not problems:
        print("No problems found in metadata file")
        return

    total_runs = len(problems) * times_per_problem
    transcript_path_obj = Path(transcript_dir)
    transcript_path_obj.mkdir(parents=True, exist_ok=True)

    pending_tasks: set[asyncio.Task] = set()
    num_completed = 0
    results = []

    async def run_one(problem, iteration: int):
        problem_id = problem["id"]
        if not re.fullmatch(r"[A-Za-z0-9][\w.-]*", problem_id):
            raise ValueError(f"refusing problem_id {problem_id!r}: invalid characters")
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        transcript_path = str(transcript_path_obj / f"{problem_id}_{timestamp}.json")

        print(
            f"problem_id={problem_id} model={model} max_tokens={max_tokens} "
            f"transcript_path={transcript_path} num_running={len(pending_tasks)} "
            f"num_runs={num_completed} total_runs={total_runs}"
        )

        async def execute_with_stream():
            grade_info = None
            try:
                async for event in await _execute_problem(
                    problem_id=problem_id,
                    image=problem["image"],
                    startup_command=problem["startup_command"],
                    model=model,
                    max_tokens=max_tokens,
                    transcript_path=transcript_path,
                    retry_config=retry_config,
                    timeout=timeout,
                    thinking_budget=thinking_budget,
                ):
                    if event.startswith("data: "):
                        try:
                            event_data = json.loads(event[6:])
                            if event_data.get("type") == "grade":
                                grade_info = event_data.get("grade", {})
                        except json.JSONDecodeError:
                            pass
            except RuntimeError as e:
                if "cancel scope" not in str(e).lower():
                    raise

            profit = 0.0
            if grade_info:
                profit = grade_info.get("profit", 0.0)
                if profit == 0.0 and "metadata" in grade_info:
                    try:
                        profit = float(grade_info["metadata"].get("profit_eth", 0.0))
                    except (ValueError, TypeError):
                        profit = 0.0

            return {
                "problem_id": problem_id,
                "success": True,
                "transcript_path": transcript_path,
                "iteration": iteration,
                "profit": profit,
            }

        try:
            return await asyncio.wait_for(execute_with_stream(), timeout=60 * timeout)
        except TimeoutError:
            print(
                f"Task timed out after {timeout} minutes: problem_id={problem_id} "
                f"iteration={iteration} transcript_path={transcript_path}"
            )
            return {
                "problem_id": problem_id,
                "success": False,
                "error": "Timeout",
                "iteration": iteration,
                "profit": 0.0,
            }
        except asyncio.CancelledError:
            print(f"Task was cancelled: problem_id={problem_id} iteration={iteration}")
            return {
                "problem_id": problem_id,
                "success": False,
                "error": "Task cancelled",
                "iteration": iteration,
                "profit": 0.0,
            }
        except Exception as e:
            return {"problem_id": problem_id, "success": False, "error": str(e), "iteration": iteration, "profit": 0.0}

    for iteration in range(times_per_problem):
        for problem in problems:
            if len(pending_tasks) >= parallel_requests:
                done, pending_tasks = await asyncio.wait(pending_tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    results.append(task.result())
                    num_completed += 1

            pending_tasks.add(asyncio.create_task(run_one(problem, iteration)))
            await asyncio.sleep(random.uniform(1, 3))

    if pending_tasks:
        done = await asyncio.gather(*pending_tasks, return_exceptions=True)
        for result in done:
            if isinstance(result, Exception):
                print(f"Task failed with exception: {result}")
            else:
                results.append(result)
                num_completed += 1

    successful = sum(1 for r in results if r["success"])
    print(f"\nEvaluation complete: {successful}/{total_runs} successful")

    errors = [r for r in results if not r["success"]]
    if errors:
        print("\nErrors encountered:")
        for error in errors:
            print(
                f"  {error['problem_id']} (iteration {error.get('iteration', '?')}): "
                f"{error.get('error', 'Unknown error')}"
            )


def main():
    parser = argparse.ArgumentParser(description="Run scone-bench evaluation")
    parser.add_argument("--max-tokens", type=int, required=True, help="Max output tokens per model turn")
    parser.add_argument("--times-per-problem", type=int, required=True, help="Attempts per problem")
    parser.add_argument("--problems-metadata", type=str, required=True, help="Path to problems metadata JSON")
    parser.add_argument("--parallel-requests", type=int, required=True, help="Max parallel containers")
    parser.add_argument("--transcript-dir", type=str, required=True, help="Where to write transcripts")
    parser.add_argument("--model", type=str, default="claude-sonnet-4-5", help="Model to use")
    parser.add_argument("--timeout", type=int, default=10, help="Per-problem timeout in minutes")
    parser.add_argument("--thinking-budget", type=int, default=10000, help="Thinking budget tokens (Claude)")

    args = parser.parse_args()

    asyncio.run(
        run_evaluation(
            max_tokens=args.max_tokens,
            times_per_problem=args.times_per_problem,
            problems_metadata_path=args.problems_metadata,
            parallel_requests=args.parallel_requests,
            transcript_dir=args.transcript_dir,
            model=args.model,
            timeout=args.timeout,
            thinking_budget=args.thinking_budget,
        )
    )


if __name__ == "__main__":
    main()
