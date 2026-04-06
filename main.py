from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SimulationParams(BaseModel):
    alpha: float
    k: float
    theta: float
    Q: float
    c1: float
    c2: float
    Delta: float

@app.post("/api/simulate")
def calculate_strategy(params: SimulationParams):
    a = params.alpha
    k = params.k
    theta = params.theta
    Q = params.Q
    Delta = params.Delta
    c1 = params.c1
    c2 = params.c2

    # ================= 1. 提取英文文献中的公共计算项 =================
    den_k2_t2 = k**2 - theta**2
    den_3k_t = 3 * k + theta
    
    # ================= 2. 基础物理量计算 (无中断基准) =================
    # 计算无中断满载产能阈值 Q'_N (文献 Proposition 1 之前的定义)
    Q_N_prime = ((2 + a) * k + a * theta) / (4 * k)
    
    # 计算产能约束调节因子 T^N (文献 Proposition 1 之前的定义)
    T_N = ((2 + a) * k + a * theta - 4 * k * Q) / (4 * k * den_3k_t)

    # 计算发生需求中断时的动态全负荷产能阈值 Q^R (文献 Proposition 2)
    if Delta <= -c2 * (k + theta):
        Q_R_prime = Q_N_prime + (Delta * (k + theta) + c2 * k * (k + theta)) / (4 * k)
    elif Delta <= c1 * k:
        Q_R_prime = Q_N_prime
    else:
        Q_R_prime = Q_N_prime + (Delta * (k + theta) - c1 * k * (k + theta)) / (4 * k)

    strategy_name = ""
    w = po = pf = qo = qf = Y_profit = Z_profit = 0.0

    # 提取常态基础利润 Y_f (文献 Proposition 4 的组成部分)
    Y_f = (2*k**2 + 4*a*k*theta + a**2*(k**2 + theta**2)) / (8*k*den_k2_t2) - (2*k*den_3k_t*T_N**2) / (k - theta)

    # ================= 3. 核心策略判定树 =================
    if Q > Q_R_prime:
        capacity_status = "产能充足 (Q > Q^R)"
        
        # 文献 Proposition 3 中的阈值定义
        Delta_c1_1 = c1 * k
        Delta_c2_1 = max(4 * k * T_N, 0) - c2 * k
        
        if Delta_c2_1 < Delta <= Delta_c1_1:
            strategy_name = "线上分配不变策略 (COA)"
            # 严格对应文献 Proposition 3 - Strategy COA 的公式
            w = (a*k + theta) / (2*den_k2_t2) + (Delta * (2*k**2 - theta**2)) / (2*k*den_k2_t2)
            pf = (k + a*theta) / (2*den_k2_t2) + (Delta * theta) / (2*den_k2_t2)
            po = (3*a*k**2 + 2*k*theta - a*theta**2) / (4*k*den_k2_t2) + (Delta * (2*k**2 - theta**2)) / (4*k*den_k2_t2)
            
            qo = a / 4 - max(T_N, 0) * k  # 产能充足下 T_N通常<=0，此处用 max 保证严格贴合文献
            qf = (2*k + a*theta) / (4*k) + (Delta * theta) / (4*k)
            
            Y_profit = (2*k**2 + 4*a*k*theta + a**2*(k**2 + theta**2)) / (8*k*den_k2_t2) + (2*Delta*(a*(k**2 + theta**2) + 2*k*theta + Delta*theta**2)) / (8*k*den_k2_t2)
            Z_profit = a**2 / (16 * k)
            
        else:
            strategy_name = "灵活分配策略 (FA)"
            # 对应文献 Proposition 3 - Strategy FA
            if Delta <= Delta_c2_1: # 负向萎缩
                w = (a*k + theta) / (2*den_k2_t2) + (Delta * k) / (2*den_k2_t2) - c2 / 2
                pf = (k + a*theta) / (2*den_k2_t2) + (Delta * theta) / (2*den_k2_t2)
                po = (3*a*k**2 + 2*k*theta - a*theta**2) / (4*k*den_k2_t2) + (Delta * (3*k**2 - theta**2)) / (4*k*den_k2_t2) - c2 / 4
                
                qo = (a + Delta + c2*k) / 4
                qf = (2*k + a*theta + Delta*theta) / (4*k) - (c2 * theta) / 2
                
                Y_profit = (2*k**2 + 4*a*k*theta + a**2*(k**2 + theta**2)) / (8*k*den_k2_t2) + (Delta*(k**2 + theta**2)*(2*a + Delta) + 4*k*theta*Delta) / (8*k*den_k2_t2) + (2*Delta*c2 + c2**2*k) / 8
                Z_profit = (a + Delta + c2 * k)**2 / (16 * k)
            else: # 正向扩张
                w = (a*k + theta) / (2*den_k2_t2) + (Delta * k) / (2*den_k2_t2) + c1 / 2
                pf = (k + a*theta) / (2*den_k2_t2) + (Delta * theta) / (2*den_k2_t2)
                po = (3*a*k**2 + 2*k*theta - a*theta**2) / (4*k*den_k2_t2) + (Delta * (3*k**2 - theta**2)) / (4*k*den_k2_t2) + c1 / 4
                
                qo = (a + Delta - c1*k) / 4
                qf = (2*k + a*theta + Delta*theta) / (4*k) + (c1 * theta) / 2
                
                Y_profit = (2*k**2 + 4*a*k*theta + a**2*(k**2 + theta**2)) / (8*k*den_k2_t2) + (Delta*(k**2 + theta**2)*(2*a + Delta) + 4*k*theta*Delta) / (8*k*den_k2_t2) - (2*Delta*c1 - c1**2*k) / 8
                Z_profit = (a + Delta - c1 * k)**2 / (16 * k)
            
    else:
        capacity_status = "产能受限 (Q <= Q^R)"
        
        # 依据英文文献数量守恒逻辑推导出的严密产能受限临界阈值
        Delta_c1_2 = c1 * (k + theta)
        Delta_c2_2 = -c2 * (k + theta)
        
        if Delta_c2_2 < Delta <= Delta_c1_2:
            strategy_name = "恒定分配策略 (CA)"
            # 严格对应文献 Proposition 4 - Strategy CA 公式
            w = (a*k + theta) / (2*den_k2_t2) + (Delta * k) / den_k2_t2 + (den_3k_t * theta * T_N) / (2*den_k2_t2) + ((2*k + theta) * T_N) / (2*den_3k_t)
            pf = (k + a*theta) / (2*den_k2_t2) + (k * T_N * den_3k_t) / den_k2_t2 + (Delta * theta) / den_k2_t2 + (k * T_N) / (k + theta)
            po = (3*a*k**2 + 2*k*theta - a*theta**2) / (4*k*den_k2_t2) + (theta * T_N * den_3k_t) / den_k2_t2 - (Delta * k) / den_k2_t2 + (k * T_N) / (k + theta)
            
            qo = a / 4 - k * T_N
            qf = (2*k + a*theta) / (4*k) - den_3k_t * T_N
            
            Y_profit = Y_f + (Delta * (k*(a - 1)*(k - theta) + 2*Q*(k + theta)**2)) / (2*den_k2_t2*den_3k_t) + (k * T_N * (T_N * den_3k_t - 4*Delta)) / (4*(k + theta))
            Z_profit = (k * (a - 1 + 2*Q)**2) / (4 * den_3k_t**2) + (a**2 * (3*k + theta**2)**2 - 4*k**2 * (a - 1 + 2*Q)**2) / (16*k * den_3k_t**2)
            
        else:
            strategy_name = "分配转移策略 (AS)"
            # 严格对应文献 Proposition 4 - Strategy AS 公式
            if Delta <= Delta_c2_2: # 负向转移
                w = (a*k + theta) / (2*den_k2_t2) + (2*k*T_N) / (k - theta) + (Delta*(4*k**2 + 3*k*theta + theta**2)) / (2*den_k2_t2*den_3k_t) - (c2*(2*k + theta)) / (2*den_3k_t)
                pf = (k + a*theta) / (2*den_k2_t2) + (2*k*T_N) / (k - theta) + (Delta*(k**2 + 5*k*theta + 2*theta**2)) / (2*den_k2_t2*den_3k_t) + (c2*k) / (2*den_3k_t)
                po = (3*a*k**2 + 2*k*theta - a*theta**2) / (4*k*den_k2_t2) + ((k + theta)*T_N) / (k - theta) - (Delta*k*(5*k + 3*theta)) / (2*den_k2_t2*den_3k_t) - (c2*k) / (2*den_3k_t)
                
                qo = a / 4 - k * T_N + (Delta * k) / (2 * den_3k_t) + (c2 * k * (k + theta)) / (2 * den_3k_t)
                qf = (2*k + a*theta) / (4*k) - (2*k + theta) * T_N - (Delta * k) / (2 * den_3k_t) - (c2 * k * (k + theta)) / (2 * den_3k_t)
                
                Y_profit = Y_f + (Delta*(2*k*(a - 1)*(k - theta) + 4*Q*(k + theta)**2) + k*Delta**2*(k - theta)) / (4*den_k2_t2*den_3k_t) + (c2*k*(2*Delta + c2*(k + theta))) / (4*den_3k_t)
                Z_profit = (k * (a - 1 + 2*Q + Delta + c2*(k + theta))**2) / (4 * den_3k_t**2)
            else: # 正向转移
                w = (a*k + theta) / (2*den_k2_t2) + (2*k*T_N) / (k - theta) + (Delta*(4*k**2 + 3*k*theta + theta**2)) / (2*den_k2_t2*den_3k_t) + (c1*(2*k + theta)) / (2*den_3k_t)
                pf = (k + a*theta) / (2*den_k2_t2) + (2*k*T_N) / (k - theta) + (Delta*(k**2 + 5*k*theta + 2*theta**2)) / (2*den_k2_t2*den_3k_t) - (c1*k) / (2*den_3k_t)
                po = (3*a*k**2 + 2*k*theta - a*theta**2) / (4*k*den_k2_t2) + ((k + theta)*T_N) / (k - theta) - (Delta*k*(5*k + 3*theta)) / (2*den_k2_t2*den_3k_t) + (c1*k) / (2*den_3k_t)
                
                qo = a / 4 - k * T_N + (Delta * k) / (2 * den_3k_t) - (c1 * k * (k + theta)) / (2 * den_3k_t)
                qf = (2*k + a*theta) / (4*k) - (2*k + theta) * T_N - (Delta * k) / (2 * den_3k_t) + (c1 * k * (k + theta)) / (2 * den_3k_t)
                
                Y_profit = Y_f + (Delta*(2*k*(a - 1)*(k - theta) + 4*Q*(k + theta)**2) + k*Delta**2*(k - theta)) / (4*den_k2_t2*den_3k_t) - (c1*k*(2*Delta - c1*(k + theta))) / (4*den_3k_t) - c1 * k * T_N
                Z_profit = (k * (a - 1 + 2*Q + Delta - c1*(k + theta))**2) / (4 * den_3k_t**2)


    # ================= 4：计算常态无中断下的真实基础利润 =================
    if Q > Q_N_prime:
        # 产能充足时的常态利润
        Y_base = (2*k**2 + 4*a*k*theta + a**2*(k**2 + theta**2)) / (8*k*den_k2_t2)
        Z_base = a**2 / (16 * k)
    else:
        # 产能受限时的常态利润
        Y_base = (2*k**2 + 4*a*k*theta + a**2*(k**2 + theta**2)) / (8*k*den_k2_t2) - (2*k*den_3k_t*T_N**2) / (k - theta)
        Z_base = a**2 / (16 * k) - ((5*a*k - 2*k + a*theta + 4*k*Q)*T_N) / den_3k_t

    # ================= 5. 组装标准 JSON 响应体返回前端 =================
    return {
        "code": 200,
        "message": "策略推演计算成功",
        "data": {
            "systemStatus": capacity_status,
            "strategy": strategy_name,
            "prices": {
                "w": round(w, 4),
                "po": round(po, 4),
                "pf": round(pf, 4)
            },
            "allocation": {
                "qo": round(qo, 4),
                "qf": round(qf, 4)
            },
            "profit": {
                "Y": round(Y_profit, 4),
                "Z": round(Z_profit, 4)
            },
            # 👇 新增：把真实的常态基础利润也传给前端
            "baseProfit": {
                "Y": round(Y_base, 4),
                "Z": round(Z_base, 4)
            }
        }
    }