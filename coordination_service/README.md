# Coordination Service

Small relay used to hand the pairing code (and later signals) between the independent
Source and Target automation invocations. See PROJECT_PLAN.md Sec 4.6 for the design and
Sec 10 (open item 4) for the still-undecided address-stability mechanism.

Run with:

```
uvicorn coordination_service.app:app --host 0.0.0.0 --port 8000
```
