"""Step 6 CLI entrypoint — local LangGraph supervisor loop (no web server)."""

import uuid

from app.session import get_session
from app.supervisor_graph import run_supervisor


def main() -> None:
    print("=" * 48)
    print(" TalentScout HR — LangGraph Supervisor (local)")
    print("=" * 48)
    print("Workers: Recruiting | HR Ops | Policy")
    print("Type 'exit' to quit.\n")
    thread_id = str(uuid.uuid4())
    session = get_session(f"graph:{thread_id}")
    while True:
        try:
            user_input = input("Recruiter: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break
        if not user_input:
            continue
        result = run_supervisor(session, user_input, thread_id=thread_id)
        print(f"\nTalentScout: {result['reply']}\n")
        for step in result.get("steps") or []:
            print(f"  · {step}")
        print()


if __name__ == "__main__":
    main()
