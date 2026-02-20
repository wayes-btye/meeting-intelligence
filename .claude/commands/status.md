Check the current project health status. Do the following:

1. Read `.issues/` directory and list all open issues (files with `open` in the name or status). Summarise each open issue in one line: ID, title, severity.
2. Run `make lint` and report pass/fail and any error count.
3. Run `pytest -m "not expensive" --tb=no -q` and report pass/fail and test count.
4. Check if `docs/work_log.md` has an entry from today — if not, flag it.
5. Report the MeetingBank data status: is data loaded in Supabase? (Check Issue #26 status.)

Present results as a concise status table. Flag any blockers that would prevent a demo.
