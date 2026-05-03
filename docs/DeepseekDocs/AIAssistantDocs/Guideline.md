Now you're wearing the right hat. Here's a practical script for you — exactly what you'd paste or say to your AI assistant (Claude Code, Cursor, Mistral Vibe, etc.) depending on what you're doing. I'll break it down by document and scenario.
The Four Documents in Your Pocket
#	File	Nickname
1	architecture_data_design.md	"The Blueprint"
2	core_flow_decision_tree.md	"The Master Flow"
3	phase_gated_checklist.md	"The Roadmap"
4	module_contract_specification.md	"The Contracts"
1. When You Start a New Phase

You're about to implement Phase 2 (Recon Agent). You've never built it before.

What you tell the AI:
text

I'm implementing Phase 2 of my Attackbot project.

Here is the Phase-Gated Checklist:
[ paste phase_gated_checklist.md ]

Here is the Core Flow & Decision Tree (look at Step 2a):
[ paste core_flow_decision_tree.md ]

Here is the Module Contract for ReconAgent:
[ paste just the ReconAgent row from module_contract_specification.md ]

I need you to write the Python code for the ReconAgent class. 
It must:
- Subscribe to the "asset.added" event.
- Run Nmap/naabu for ports, Wappalyzer for tech stack, gospider for URLs.
- Publish a "recon.completed" event with a JSON summary.
- Respect the "in_scope" field from the asset.

Why this works: The AI sees what phase you're on, where it fits in the flow, and the exact contract.
2. When You Connect Two Modules

You've built ReconAgent and GoalActPlanner separately. Now they need to talk.

What you tell the AI:
text

I need to wire the ReconAgent to the GoalActPlanner via NATS.

Here are their contracts:
[ paste ReconAgent and GoalActPlanner rows from module_contract_specification.md ]

ReconAgent publishes "recon.completed". GoalActPlanner subscribes to that.
Write the NATS subscription code for GoalActPlanner that triggers a replan when recon data arrives.

No need for the full architecture doc – the contracts have the events.
3. When You're Debugging a Broken Behavior

Something went wrong. GoalAct is trying to exploit an out-of-scope asset.

What you tell the AI:
text

My system just tried to attack an out-of-scope URL. 
According to the Core Flow Decision Tree, the ScopeEnforcer should block that.
Here is the relevant part of the flow:
[ paste the "2b. Exploit" section with the ScopeEnforcer check ]

Here is the ScopeEnforcer contract:
[ paste ScopeEnforcer row ]

The logs show the action went through without being checked. Where is the bug?

4. When You Need Infrastructure

You're setting up Docker Compose for the first time.

What you tell the AI:
text

I'm setting up the data infrastructure for Attackbot.

Here is the Architecture & Data Design Blueprint:
[ paste architecture_data_design.md ]

Please generate a Docker Compose file that includes PostgreSQL with pgvector, Valkey, and NATS.

The blueprint lists all components and their purposes. The AI knows the stack.
5. When You Want to Add a New Feature (e.g., JavaScript Analysis)

You want to extend ReconAgent to also deobfuscate JavaScript.

What you tell the AI:
text

I want to add JavaScript deobfuscation to my ReconAgent.

Here is the current ReconAgent contract:
[ paste ReconAgent row ]

Here is the Architecture doc (look at the Adapter pattern):
[ paste Architecture section 3.6 ]

My architecture says I should wrap external tools in an Adapter. 
Should I create a new module, or extend ReconAgent? Give me a recommendation and updated contract.

The AI will reason within the architecture instead of making ad-hoc changes.
6. When You Want to Verify Phase Completion

Phase 6 (Branching) is done, you've seen the logs, but you want a second opinion.

What you tell the AI:
text

Here is the Phase-Gated Checklist, Phase 6:
[ paste Phase 6 row ]

Here are the last 100 lines of my agent logs:
[ paste logs ]

Does this output satisfy the "Testable Output" column? Should I move to Phase 7?

The Golden Rule (Tell the AI This Once)

At the very beginning of your project session, tell the AI:
text

These four documents are my constitution:
- architecture_data_design.md
- core_flow_decision_tree.md
- phase_gated_checklist.md
- module_contract_specification.md

You may read and reference them, but you are NEVER allowed to modify them 
unless I explicitly say: "Update the document." 
If you think a change is needed, ask me first.

This single rule prevents the AI from quietly rewriting your anchors.
Quick Reference Card for You
Task	Feed the AI this
Start a new phase	Checklist + Flow + Contract of the module
Wire modules together	Contracts of both modules
Debug a broken chain	Flow (relevant section) + Contract of suspicious module
Add infra/storage	Architecture doc
Add new tool/module	Architecture doc (patterns) + nearest existing contract
Check phase completion	Checklist + logs
Change architecture	Ask AI to propose change, then YOU update the doc before implementing

That's your playbook. You're now the AI's project manager, not the other way around