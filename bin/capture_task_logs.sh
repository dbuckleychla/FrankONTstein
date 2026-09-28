#!/usr/bin/env bash
# Source inside the task script so logs exist before executor output staging.
# Keep console streaming, drain both tee processes, and preserve task exit status.
mkdir -p "runtime_logs/$1"
exec 3>&1 4>&2
rm -f .fot_stdout.pipe .fot_stderr.pipe
mkfifo .fot_stdout.pipe .fot_stderr.pipe
tee "runtime_logs/$1/stdout.log" < .fot_stdout.pipe >&3 &
fot_stdout_logger=$!
tee "runtime_logs/$1/stderr.log" < .fot_stderr.pipe >&4 &
fot_stderr_logger=$!
exec > .fot_stdout.pipe 2> .fot_stderr.pipe
trap 'fot_task_status=$?; trap - EXIT; exec 1>&3 2>&4; wait "$fot_stdout_logger" || true; wait "$fot_stderr_logger" || true; rm -f .fot_stdout.pipe .fot_stderr.pipe; exit "$fot_task_status"' EXIT
