class Result_State:
    CONFIRMED_FINDING = "CONFIRMED_FINDING"  # ran correctly, found something
    CONFIRMED_EMPTY = "CONFIRMED_EMPTY"      # ran correctly, genuinely nothing
    EXECUTION_FAILED = "EXECUTION_FAILED"    # did not run correctly — retry or fallback