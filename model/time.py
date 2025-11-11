from pyomo.environ import Set, Param, NonNegativeReals, NonNegativeIntegers

def build_time(m, blocks_data):
    m.SB = Set(dimen=2, ordered=True, initialize=blocks_data["sb_list"])
    sb_with_succ = list(blocks_data["succ_stage"].keys())
    m.SB_SUCC = Set(dimen=2, ordered=False, initialize=sb_with_succ)

    m.Duration  = Param(m.SB, initialize=blocks_data["duration"])
    m.SuccStage = Param(m.SB_SUCC, initialize=blocks_data["succ_stage"])
    m.SuccBlock = Param(m.SB_SUCC, initialize=blocks_data["succ_block"])

    # set de stages
    m.STAGES = Set(initialize=sorted(blocks_data["stage_year"].keys())) 

    # calendario indexado por stage
    m.StageYear  = Param(m.STAGES, initialize=blocks_data["stage_year"],  within=NonNegativeIntegers)
    m.StageMonth = Param(m.STAGES, initialize=blocks_data["stage_month"], within=NonNegativeIntegers)

    return m
