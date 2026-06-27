## Attribute Usecase

1. handle = Allows us to hit the hacker/program{handle}/structured_scopes endpoint to get program specific information
2. submission_state = Only target those whose submission_state is "open", "disabled", or "paused"
3. offers_bounties = Only target those whose offer_bounties = true
4. open_scope = Allows us to target potential "assets" which are not explicitly mentioned in scope (more converage, higher value)
5. policy = Highlevel guidelines for a specific program
6. gold_standard_safe_harbor = If true, publisher won't pursue attackers who act in good faith. Target programs whose value is "true"7