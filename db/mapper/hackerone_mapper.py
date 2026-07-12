class HackerOneMapper:
    @staticmethod
    def map_program(program: dict) -> dict:
        return {
            "master": HackerOneMapper._map_master(program),
            "scopes": HackerOneMapper._map_scopes(program.get("scopes", [])),
            "weaknesses": HackerOneMapper._map_weaknesses(program.get("weaknesses", [])),
            "exclusions": HackerOneMapper._map_exclusions(
                program.get("exclusions", [])
            ),
        }

    @staticmethod
    def _map_master(program: dict) -> dict:
        return {
            "handle": program["handle"],
            "scope_count": program["scope_count"],
        }

    @staticmethod
    def _map_scopes(scopes: list[dict]) -> list[dict]:
        return [
            {
                "scope_type": scope.get("asset_type"),
                "scope_identifier": scope.get("asset_identifier"),
                "max_severity": scope.get("max_severity"),
                "scope_instructions": scope.get("instruction"),
            }
            for scope in scopes
        ]

    @staticmethod
    def _map_weaknesses(weaknesses: list[dict]) -> list[dict]:
        mapped = []

        for weakness in weaknesses:
            attrs = weakness.get("attributes", {})

            mapped.append(
                {
                    "weakness_id": weakness.get("id"),
                    "weakness_name": attrs.get("name"),
                    "weakness_description": attrs.get("description"),
                }
            )

        return mapped

    @staticmethod
    def _map_exclusions(exclusions: list[dict]) -> list[dict]:
        mapped = []

        for exclusion in exclusions:
            attrs = exclusion.get("attributes", {})

            mapped.append(
                {
                    "exclusion_category": attrs.get("category"),
                    "exclusion_details": attrs.get("details"),
                }
            )

        return mapped