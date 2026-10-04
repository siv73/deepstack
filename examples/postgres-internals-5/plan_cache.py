"""How a prepared statement chooses a custom or a generic plan (modelled on plancache.c in PostgreSQL 18)."""

from statistics import mean

CPU_OPERATOR_COST = 0.0025


def planning_charge(n_relations: int) -> float:
    """Custom plans are charged for planning: 1000 * cpu_operator_cost * (relations + 1)."""
    return 1000 * CPU_OPERATOR_COST * (n_relations + 1)


class PreparedStatement:
    def __init__(self, custom_cost, generic_cost, n_relations=1, mode="auto"):
        self.custom_cost = custom_cost  # value -> estimated cost of a plan made for that value
        self.generic_cost = generic_cost  # estimated cost of the one plan made without values
        self.n_relations = n_relations
        self.mode = mode  # plan_cache_mode: auto, force_custom_plan, force_generic_plan
        self.custom_costs: list[float] = []

    def _wants_custom(self) -> bool:
        if self.mode == "force_generic_plan":
            return False
        if self.mode == "force_custom_plan":
            return True
        if len(self.custom_costs) < 5:  # the first five executions always get custom plans
            return True
        return not self.generic_cost < mean(self.custom_costs)

    def execute(self, value) -> str:
        if self._wants_custom():
            self.custom_costs.append(self.custom_cost(value) + planning_charge(self.n_relations))
            return "custom"
        return "generic"
