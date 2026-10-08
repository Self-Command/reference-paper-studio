# 具有保护约束的周期时频冲突消解模型

针对有限次数重复占用时频资源的任务集合，建立具有保护约束的周期时频冲突消解模型。以任务的合法动作为有限决策域，以动作占用集合的交叠关系构造冲突禁配约束，并按优先级撤销数量、调整数量及归一化调整幅度进行字典序优化。模型允许任务属性、优先级数量和动作权限异质化，通过统一占用定义描述频移、时移及间隔调整。

## 1. 问题描述与模型假设

设有一组已经给定初始计划的任务。每个任务在连续频段内工作，在时间轴上以固定空闲间隔重复使用有限次。不同任务的带宽、单次持续时间、首次开始时刻、间隔、次数、优先级和调整权限均可不同。

模型适用的条件如下：

1. 时间和频率已按基本单元离散，全部坐标为整数；使用半开区间。
2. 同一时频单元在同一时刻最多由一个未撤销任务占用。
3. 频移和时移作用于任务全部重复使用；间隔调整改变重复窗口之间的空闲时间。
4. 一个任务最多调整一个参数，带宽、单次持续时间和重复次数固定。
5. 参数是确定的，任务数量和调整幅度有限。保护集合、截止时刻与目标策略在求解前确定。

任务属性与优先级独立设置，同一等级内允许存在不同的带宽、时长、间隔、次数和动作权限。模型采用确定性、离散坐标和单位容量的资源互斥假设。

## 2. 参数、符号及原始占用

### 2.1 输入参数

| 符号 | 含义与条件 |
|---|---|
| \(\mathcal J=\{1,\ldots,N\}\) | 任务集合，\(N\ge1\)；任务标识与优先级独立 |
| \(L,\ell_i\) | 优先级数量与任务等级，\(L\ge1,\ell_i\in\{1,\ldots,L\}\)，1 为最高等级 |
| \(\mathcal P\subseteq\mathcal J\) | 不可撤销的保护集合，允许为空 |
| \(F\) | 频率资源宽度，\(F\in\mathbb Z_{>0}\)，范围为 \([0,F)\) |
| \(a_i,w_i\) | 原频率起点与带宽，\(a_i\in\mathbb Z_{\ge0},w_i\in\mathbb Z_{>0},a_i+w_i\le F\) |
| \(t_i,d_i\) | 首次开始时刻与单次持续时间，\(t_i\in\mathbb Z_{\ge0},d_i\in\mathbb Z_{>0}\) |
| \(g_i,n_i\) | 原空闲间隔与重复次数，\(g_i\in\mathbb Z_{\ge0},n_i\in\mathbb Z_{>0}\) |
| \(\Gamma_i\subseteq\{\mathrm F,\mathrm T,\mathrm G\}\) | 允许调整的参数种类：频率、首次开始时刻、空闲间隔 |
| \(B_i^{\mathrm F},B_i^{\mathrm T},B_i^{\mathrm G}\) | 各方向的非负整数调整上限；上限为 0 时无非零调整 |
| \(H\) | 可选的正整数业务截止时刻；未提供时不额外限制任务结束时刻 |
| \(\rho_{\mathrm F},\rho_{\mathrm T},\rho_{\mathrm G}\) | 固定的正整数幅度参考尺度，与调整上限分别设置 |
| \(\pi\in\{P,T\}\) | 目标策略，\(P\) 为优先级优先，\(T\) 为总撤销量优先 |

输入中的间隔 \(g_i\) 始终表示“前一次使用结束到下一次使用开始”的空闲时长。开始到开始的周期为：

\[
p_i=d_i+g_i,\qquad
I_{ik}^{0}=[t_i+k p_i,\ t_i+k p_i+d_i),\quad k=0,\ldots,n_i-1.
\tag{M1}
\]

频段为 \([a_i,a_i+w_i)\)。任务的原始占用是该频段与每个 \(I_{ik}^{0}\) 的笛卡尔积之并；周期内的空闲时间可以由其他任务使用。

## 3. 合法动作域

### 3.1 单参数动作

任务 \(i\) 的非撤销动作以整数三元组
\(s=(\delta^{\mathrm F}_{is},\delta^{\mathrm T}_{is},\delta^{\mathrm G}_{is})\)
表示，分别对应频移、整体时移和空闲间隔调整。保持动作记为 \(s^0=(0,0,0)\)。

先定义未经过资源边界筛选的候选动作集合：

\[
\Omega_i=
\left\{
s\in\mathbb Z^3:
\begin{array}{l}
|\delta^r_{is}|\le B_i^r,\quad r\in\{\mathrm F,\mathrm T,\mathrm G\},\\
\delta^r_{is}=0,\quad r\notin\Gamma_i,\\
\displaystyle\sum_{r\in\{\mathrm F,\mathrm T,\mathrm G\}}
\mathbf 1\{\delta^r_{is}\ne0\}\le1
\end{array}
\right\}.
\tag{M2}
\]

三种零平移统一为保持动作，不重复建立“频移 0”“时移 0”等状态。基础模型取 \(\Gamma_i\subseteq\{\mathrm F,\mathrm T\}\)；允许调整空闲间隔时，令相应任务满足 \(\mathrm G\in\Gamma_i\)。

### 3.2 调整后的占用

对 \(s\in\Omega_i\)，定义：

\[
\begin{aligned}
a_i(s)&=a_i+\delta^{\mathrm F}_{is},\\
t_i(s)&=t_i+\delta^{\mathrm T}_{is},\\
g_i(s)&=g_i+\delta^{\mathrm G}_{is},\\
p_i(s)&=d_i+g_i(s),\\
u_{ik}(s)&=t_i(s)+k p_i(s).
\end{aligned}
\tag{M3}
\]

全部时频占用为：

\[
R_i(s)=
\bigcup_{k=0}^{n_i-1}
[a_i(s),a_i(s)+w_i)
\times
[u_{ik}(s),u_{ik}(s)+d_i).
\tag{M4}
\]

最后一次使用的结束时刻为：

\[
e_i(s)=t_i(s)+(n_i-1)p_i(s)+d_i.
\tag{M5}
\]

频移改变全部重复使用的共用频段；时移对全部窗口施加同一个平移量。间隔调整使第 \(k\) 次使用的开始时刻改变 \(k\delta^{\mathrm G}_{is}\)，故它与整体时移的作用不同。

一个计划应表示为多个周期矩形的并集，不能把从第一次开始到最后一次结束之间的整个跨度视为持续占用。

### 3.3 边界及保护条件

定义合法非撤销动作域：

\[
S_i^+=
\left\{
s\in\Omega_i:
\begin{array}{l}
0\le a_i(s),\quad a_i(s)+w_i\le F,\\
t_i(s)\ge0,\quad g_i(s)\ge0,\\
e_i(s)\le H\quad\text{（仅在提供业务截止时刻时）}
\end{array}
\right\}.
\tag{M6}
\]

由于 \(d_i>0\) 且 \(g_i(s)\ge0\)，同一任务的重复窗口不会自重叠，最后一次结束边界足以约束全部使用。

撤销动作记为 \(\bot\)，其占用为 \(R_i(\bot)=\varnothing\)。最终动作域为：

\[
S_i=
\begin{cases}
S_i^+, & i\in\mathcal P,\\
S_i^+\cup\{\bot\}, & i\notin\mathcal P.
\end{cases}
\tag{M7}
\]

普通任务在没有合法非撤销动作时只能撤销。保护任务的动作域为空时，当前实例不可行。保护并不保证任务无需调整，而是禁止选择撤销动作。

优先级与保护分别输入：高优先级表达优化顺序，保护集合表达必须执行的业务条件。

## 4. 冲突关系的精确定义

两个半开区间只有在交集长度严格大于 0 时才重叠，端点相接不产生冲突。

对两个非撤销动作，频率交叠条件为：

\[
O^{\mathrm F}_{ij}(s,r)=
\mathbf 1\!\left\{
\max(a_i(s),a_j(r))
<
\min(a_i(s)+w_i,a_j(r)+w_j)
\right\}.
\tag{M8}
\]

第 \(k\) 和第 \(h\) 次使用的时间交叠条件为：

\[
O^{\mathrm T}_{ij,kh}(s,r)=
\mathbf 1\!\left\{
\max(u_{ik}(s),u_{jh}(r))
<
\min(u_{ik}(s)+d_i,u_{jh}(r)+d_j)
\right\}.
\tag{M9}
\]

完整动作冲突常量为：

\[
C_{ij}(s,r)=
\begin{cases}
0, & s=\bot\ \text{或}\ r=\bot,\\
O^{\mathrm F}_{ij}(s,r)
\mathbf 1\!\left\{
\exists k\in\{0,\ldots,n_i-1\},
h\in\{0,\ldots,n_j-1\}:
O^{\mathrm T}_{ij,kh}(s,r)=1
\right\}, & \text{其余情况}.
\end{cases}
\tag{M10}
\]

该定义与 \(R_i(s)\cap R_j(r)\ne\varnothing\) 完全一致。只有频率交叠或只有时间交叠均不足以构成时频冲突。

所有约束根据调整后动作生成。一个原本无冲突的任务对可能因调整产生新冲突，因而不能只为原始冲突清单建立约束。安全预筛选可以检查两台任务全部合法非撤销占用的并集是否相交。

## 5. 约束规划模型及等价表示

### 5.1 有限域动作表示

每个任务设置一个动作变量：

\[
A_i\in S_i,\qquad i\in\mathcal J.
\tag{M11}
\]

对每对任务建立禁配表：

\[
\mathcal F_{ij}
=
\{(s,r)\in S_i\times S_j:C_{ij}(s,r)=1\},
\qquad i<j.
\tag{M12}
\]

可行性约束为：

\[
(A_i,A_j)\notin\mathcal F_{ij},\qquad \forall i<j.
\tag{M13}
\]

一个动作变量恰好取一个状态。权限、幅度、边界和保护已包含在合法域中。求解器使用每个任务自身的连续整数状态编号，通过禁配表约束表达式 (M13)。

### 5.2 0-1 状态表示

定义 \(x_{is}=1\) 表示任务 \(i\) 选择动作 \(s\)：

\[
\sum_{s\in S_i}x_{is}=1,\qquad
x_{is}\in\{0,1\},\qquad \forall i.
\tag{M14}
\]

对每个冲突动作组合施加：

\[
x_{is}+x_{jr}\le1,\qquad
\forall i<j,\ (s,r)\in\mathcal F_{ij}.
\tag{M15}
\]

这给出带分组选择约束的状态冲突图表示：每个任务是一组互斥状态，组间冲突由边表示。该表示无需为动作乘积另外设置辅助变量。

### 5.3 单位资源表示

取包含全部合法占用的有限整数包络 \(H^*\)，其确定方式见第 7.1 节。定义单元索引及实际单元：

\[
\begin{aligned}
Q&=\{0,\ldots,F-1\}\times\{0,\ldots,H^*-1\},\\
E_{f,\tau}&=[f,f+1)\times[\tau,\tau+1),\\
b_{q,is}&=\mathbf 1\{E_q\subseteq R_i(s)\}.
\end{aligned}
\tag{M16}
\]

资源互斥也可表示为：

\[
\sum_i\sum_{s\in S_i}b_{q,is}x_{is}\le1,\qquad \forall q\in Q.
\tag{M17}
\]

式 (M14)(M17) 可以替代式 (M14)(M15)，两种形式不必同时建立。它们与有限域禁配模型具有相同的可行方案和目标值，证明见第 8 节。

上述等价关系建立在整数坐标和单位容量条件下。

## 6. 目标函数与完整优化模型

### 6.1 任务损失和计划扰动

对每个动作定义撤销、调整和未变指标：

\[
\begin{aligned}
D_i(s)&=\mathbf 1\{s=\bot\},\\
M_i(s)&=\mathbf 1\{s\in S_i^+,\ s\ne s^0\},\\
U_i(s)&=1-D_i(s)-M_i(s).
\end{aligned}
\tag{M18}
\]

保持动作被边界删除时，任务域中自然没有 \(U_i=1\) 的选择。未撤销数量为 \(U_i+M_i\)，不把“未撤销”和“未调整”混称为保留。

定义无量纲幅度成本：

\[
c_i(s)=
\begin{cases}
0, & s=\bot,\\
\displaystyle
\frac{|\delta^{\mathrm F}_{is}|}{\rho_{\mathrm F}}
+
\frac{|\delta^{\mathrm T}_{is}|}{\rho_{\mathrm T}}
+
\frac{|\delta^{\mathrm G}_{is}|}{\rho_{\mathrm G}},
& s\in S_i^+.
\end{cases}
\tag{M19}
\]

参考尺度表示比较不同参数变化时采用的基准。它们在一组实验中固定，不能因动作上限改变而同步改变，否则比较的目标函数也发生变化。

按等级和总体汇总：

\[
\begin{aligned}
D_\ell(x)&=\sum_{i:\ell_i=\ell}\sum_{s\in S_i}D_i(s)x_{is},\\
M_\ell(x)&=\sum_{i:\ell_i=\ell}\sum_{s\in S_i}M_i(s)x_{is},\\
D_{\mathrm{all}}(x)&=\sum_{\ell=1}^{L}D_\ell(x),\\
M_{\mathrm{all}}(x)&=\sum_{\ell=1}^{L}M_\ell(x),\\
C_{\mathrm{move}}(x)&=\sum_i\sum_{s\in S_i}c_i(s)x_{is}.
\end{aligned}
\tag{M20}
\]

### 6.2 优先级分层目标

主模型按等级依次最小化撤销数量，再最小化调整数量，最后最小化调整幅度：

\[
\min_{\mathrm{lex}}
\Phi_P(x)
=
\left(
D_1(x),D_2(x),\ldots,D_L(x),
M_{\mathrm{all}}(x),
C_{\mathrm{move}}(x)
\right).
\tag{M21}
\]

字典序的含义是：比较两个方案时，先比较第一个分量；只有前面的分量全部相同，才比较后续分量。它严格表达目标的先后顺序，不需要选择类别撤销惩罚权重。

这一策略允许为了减少一个较高等级任务的撤销而撤销更多较低等级任务。所有等级撤销数均须列入，因为没有先固定总撤销数量。保护导致恒为 0 的分量可跳过实际求解，但仍保留在输出向量中。

采用整数目标求解时，取：

\[
K=\operatorname{lcm}
(\rho_{\mathrm F},\rho_{\mathrm T},\rho_{\mathrm G}),\qquad
\widehat c_i(s)=Kc_i(s),\qquad
\widehat C_{\mathrm{move}}=KC_{\mathrm{move}}.
\tag{M22}
\]

所有 \(\widehat c_i\) 均为整数。统一乘以正数保持幅度目标的排序。

### 6.3 总撤销量优先目标

当总体撤销数量优先于各等级撤销数量时，目标定义为：

\[
\min_{\mathrm{lex}}
\Phi_T(x)=
\left(
D_{\mathrm{all}},
D_1,\ldots,D_{L-1},
M_{\mathrm{all}},
M_1,\ldots,M_{L-1},
C_{\mathrm{move}}
\right).
\tag{M23}
\]

先固定总撤销和总调整后，最低等级计数由其余等级计数确定，因此不用重复列入。\(L=1\) 时两个等级前缀为空，只剩总撤销、总调整和幅度成本。

保护集合适用于两种目标策略。改变保护集合会改变可行域，而改变目标顺序只改变可行方案之间的偏好。

### 6.4 完整主模型

设 \(S_i\)、\(\mathcal F_{ij}\)、各指标与成本按前述定义生成。完整优化问题可统一写为：

\[
\boxed{
\begin{aligned}
\min_{\mathrm{lex}}\quad&
(D_1(x),\ldots,D_L(x),M_{\mathrm{all}}(x),C_{\mathrm{move}}(x))\\
\mathrm{s.t.}\quad&
\sum_{s\in S_i}x_{is}=1,\qquad \forall i\in\mathcal J,\\
&
x_{is}+x_{jr}\le1,\qquad
\forall i<j,\ (s,r)\in\mathcal F_{ij},\\
&
x_{is}\in\{0,1\},\qquad \forall i,\ s\in S_i.
\end{aligned}
}
\tag{M24}
\]

其中，单参数调整、幅度限制、时频边界、可选截止和保护由动作域 (M2)—(M7) 完整体现。有限域约束规划表示与式 (M24) 对应同一个优化问题。

## 7. 模型扩展

### 7.1 有限时域包络

提供业务截止时刻时，令 \(H^*=H\)。未提供时，由合法状态计算：

\[
H^*=\bar H=
\max\!\left(
\{0\}\cup
\{e_i(s):i\in\mathcal J,\ s\in S_i^+\}
\right).
\tag{M25}
\]

有限动作域与有限重复次数保证 \(\bar H\) 有限。该包络用于单位资源表示，与业务截止时刻分别定义。所有非撤销域都为空时，\(\bar H=0\)，单位资源集合为空；可行性由保护条件和动作选择约束决定。

对固定时域内的不同动作配置进行比较时，采用相同的业务截止时刻 \(H\)。

### 7.2 间隔调整

对获准任务允许 \(\mathrm G\in\Gamma_i\)，以 \(B_i^{\mathrm G}\) 控制调整幅度，其余占用定义、互斥约束及目标保持一致。

在其余条件与参考尺度不变时，增加合法动作只会扩大可行域，最优字典序向量不会变差。但某个较低等级的撤销分量可能增加：较高等级改善后，字典序允许这种取舍。

### 7.3 固定方案扩容

设一组既有任务动作已给定，并满足频率范围 \([0,F)\)、有限时域 \([0,H)\) 内的边界及资源互斥约束。在该方案固定的条件下，接纳尽可能多的新增任务。

设新增任务统一模板为 \((w^+,d^+,g^+,n^+)\)，其中 \(w^+,d^+,n^+>0,g^+\ge0\)。其周期和总跨度为：

\[
p^+=d^++g^+,\qquad
T^+=n^+d^++(n^+-1)g^+.
\tag{M26}
\]

候选位置集合为：

\[
\mathcal C=
\{(f,t)\in\mathbb Z_{\ge0}^2:
f+w^+\le F,\quad t+T^+\le H\}.
\tag{M27}
\]

候选 \(p=(f,t)\) 的占用按式 (M4) 生成。每个位置只生成一次。模板带宽或跨度超过资源范围时，\(\mathcal C=\varnothing\)，新增最优值为 0。

令 \(b_q^0\in\{0,1\}\) 为冻结方案在单元 \(q\) 的占用，\(b_{q,p}\) 为新增候选占用，\(y_p=1\) 表示接纳该候选：

\[
\begin{aligned}
\max\quad&\sum_{p\in\mathcal C}y_p\\
\mathrm{s.t.}\quad&
b_q^0+\sum_{p\in\mathcal C}b_{q,p}y_p\le1,\qquad \forall q\in Q,\\
&y_p\in\{0,1\},\qquad \forall p\in\mathcal C.
\end{aligned}
\tag{M28}
\]

这是相同资源互斥内核上的集合打包扩展。它求给定冻结方案下的接纳量，既有任务动作不参与重新优化。

## 8. 模型性质

在整数坐标、单位容量与有限动作域假设下，模型具有以下性质。

### 命题 1：动作域可靠且完整

任何满足动作权限、整数幅度、单参数及边界条件的非撤销业务动作，都属于 \(\Omega_i\) 并通过 (M6) 的筛选；反之，\(S_i^+\) 中每个动作都满足这些条件。普通任务另有撤销动作，保护任务没有撤销动作。

因此，未去重的合法动作域与允许的业务动作一致。一个动作变量或一组恰选一个状态的 0-1 变量，均表达一个合法任务决策。

### 命题 2：二元禁配与无冲突互为充要条件

若已选占用两两无交叠，则任意所选动作对的 \(C_{ij}\) 为 0，不会命中禁配表。反之，只要存在交叠任务，就存在相应动作对满足 \(C_{ij}=1\)，违反 (M13) 或 (M15)。

因此，禁配约束不遗漏调整产生的新冲突，也不排除任何按本模型互斥规则合法的方案。

### 命题 3：三种表示等价

有限域动作选择与恰选一个状态的 0-1 变量一一对应。整数坐标的半开矩形若交集非空，交集至少包含一个基本时频单元；共占一个基本单元也必然相交。

故 (M13)、(M14)(M15)、(M14)(M17) 对相同动作域产生相同的可行方案；使用同一指标函数后，目标值也相同。

### 命题 4：相同占用的安全去重保持最优值

若同一任务两个动作的占用完全相同，则它们与其他任务的冲突关系相同。只有保留动作的完整目标贡献向量在当前策略下不劣时，才可以删除另一个动作。

任意使用被删动作的方案可替换为保留动作，保持可行性且不恶化目标。因此安全去重保留最优值，但不要求保留所有冗余动作编码。单次使用任务的间隔调整不改变占用，合法保持动作优于这类无效调整。

### 命题 5：全模型可行性取决于保护子系统

若全模型可行，其保护任务对应的动作组合当然可行。反之，若保护子系统存在兼容的合法非撤销动作，则为所有普通任务选择撤销即可构造全模型可行方案。

因此，全模型可行当且仅当保护任务子系统可行。保护集合为空时，全撤销给出可行方案；是否能获得有价值的服务保留，由优化目标决定。

### 命题 6：逐层最优固定得到字典序最优

在原可行域中求第一层最优值，并固定该值；在受此限制的域中求第二层最优值，依此类推。归纳可知，每一层均在所有前层最优的方案中优化。全部层均已证明最优后，最终方案为字典序最优。

只得到可行值而未证明最优时，不能据此固定该层并声称后续方案为全模型字典序最优。

## 9. 求解方法

### 9.1 字典序约束规划求解

以 CP-SAT 为求解工具，采用有限域动作变量和二元禁配表建立模型。将式 (M21) 的目标依次记为 \(f_1,\ldots,f_{L+2}\)，其中最后一层使用整数化幅度 \(\widehat C_{\mathrm{move}}\)。求解过程如下：

1. 根据参数生成合法动作域，删除非法动作，并对相同占用的被支配动作进行安全去重。
2. 计算动作冲突常量，生成任务对的禁配表，建立有限域约束规划模型。
3. 在原可行域中最小化 \(f_1\)，得到最优值 \(z_1^*\) 后加入 \(f_1=z_1^*\)。
4. 对 \(q=2,\ldots,L+2\)，在已固定的前层最优约束下最小化 \(f_q\)，证明最优后加入 \(f_q=z_q^*\)。
5. 提取动作选择及对应周期窗口，计算撤销数量、调整数量和归一化幅度。

总撤销量优先目标 (M23) 按其分量顺序使用相同求解步骤。启发式方法可为约束规划提供可行解和搜索提示。

### 9.2 逻辑 Benders 分解

采用逻辑 Benders 分解，将撤销选择作为主问题，以未撤销任务的合法状态选择作为可行性子问题。记 \(D_i=\sum_{s\in S_i}D_i(s)x_{is}\)。设 \(\mathcal K\) 是已经证明“全部保留时无兼容非撤销动作”的任务核心，则任何可行方案都必须至少撤销一个非保护任务：

\[
\sum_{i\in\mathcal K\setminus\mathcal P}D_i\ge1.
\tag{M29}
\]

核心全部属于保护集合时，保护配置不可行。未决状态不能生成这种割。缩小核心时，只能删除经过再次证明仍不可行后允许删除的任务。

主问题按所选策略优化撤销前缀。完成撤销前缀后，仅固定各层最优计数，回到完整模型优化调整和幅度；不固定某一组撤销任务，以免丢失相同撤销向量下的更优方案。

### 9.3 最优性判定

设第 \(q\) 层当前可行目标值为 \(z_q\)，有效下界为 \(\underline z_q\)。只有在本层最优性已经证明时，才固定该层值并继续下一层。若证明 \(z_q=\underline z_q\)，且全部前层均已证明最优，则前 \(q\) 层构成精确最优前缀。

限时搜索得到可行解但尚未证明最优时，该解提供上界；搜索未决不构成不可行证明。逻辑 Benders 割仅由已证明不可行的子问题生成。前层已固定的合法见证仍应属于后层可行域。

### 9.4 构造规模

未经边界筛选和去重时，每个任务状态数满足：

\[
|S_i|
\le
1+2\sum_{r\in\Gamma_i}B_i^r
+\mathbf 1\{i\notin\mathcal P\}.
\tag{M30}
\]

设状态数上限为 \(S_{\max}\)，重复次数上限为 \(n_{\max}\)。采用频率预筛选和有序时间窗口扫描，禁配生成最坏时间为 \(O(N^2S_{\max}^2n_{\max})\)，禁配条目最多 \(O(N^2S_{\max}^2)\)。

有限域表示有 \(N\) 个动作变量，0-1 表示有 \(\sum_i|S_i|\) 个状态变量。单位资源表示的非零项规模取决于各状态占用面积。

## 10. 参考文献

[1] Yuan Y, Bahl P, Chandra R, et al. Allocating dynamic time-spectrum blocks in cognitive radio networks[C]//Proceedings of MobiHoc. 2007. [全文](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/bsmart.pdf).

[2] Aardal K I, van Hoesel S P M, Koster A M C A, et al. Models and solution techniques for frequency assignment problems[J]. Annals of Operations Research, 2007, 153: 79-129. [全文](https://link.springer.com/content/pdf/10.1007/s10479-007-0178-0.pdf).

[3] Halldórsson M M, Tonoyan T. Universal framework for wireless scheduling problems[C]//Proceedings of ICALP. 2017. [全文](https://arxiv.org/pdf/1705.10104).

[4] Letsios D, Mistry M, Misener R. Exact lexicographic scheduling and approximate rescheduling[J]. European Journal of Operational Research, 2021, 290(2): 469-478. [全文](https://arxiv.org/pdf/1805.03437).

[5] Ciré A A, Çoban E, Hooker J N. Logic-based Benders decomposition for planning and scheduling: a computational analysis[J]. The Knowledge Engineering Review, 2016, 31(5): 440-451. [全文](https://maxapress.com/data/article/ker/preview/pdf/S0269888916000254.pdf).

[6] Rossi F, van Beek P, Walsh T, eds. Handbook of Constraint Programming[M]. Elsevier, 2006. [出版记录](https://shop.elsevier.com/books/handbook-of-constraint-programming/rossi/978-0-444-52726-4).
