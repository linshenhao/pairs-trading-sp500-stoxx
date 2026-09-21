<div align="center">

# Walk-Forward Pairs Trading：S&P 500 与 STOXX 600 配对交易研究

<p><strong>一项覆盖美国与欧洲股票市场、重视诚实评估和可复现性的市场中性统计套利研究。</strong></p>

<p>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/pandas-Data%20Analysis-150458?logo=pandas&logoColor=white" alt="pandas">
  <img src="https://img.shields.io/badge/statsmodels-Econometrics-4C78A8" alt="statsmodels">
  <img src="https://img.shields.io/badge/Jupyter-Notebook-F37626?logo=jupyter&logoColor=white" alt="Jupyter">
  <img src="https://img.shields.io/badge/Matplotlib-Visualization-11557C" alt="Matplotlib">
</p>

<p>
  <a href="https://github.com/linshenhao"><img src="https://img.shields.io/badge/GitHub-Stefano%20Lin-181717?logo=github&logoColor=white" alt="GitHub"></a>
  <a href="https://www.linkedin.com/in/linshenhao-49b127393"><img src="https://img.shields.io/badge/LinkedIn-Stefano%20Lin-0A66C2?logo=linkedin&logoColor=white" alt="LinkedIn"></a>
</p>

<p><a href="README.md">English</a> | <strong>简体中文</strong></p>

</div>

---

这是一个以 **S&P 500** 和 **STOXX 600** 为股票池的配对交易（Pairs Trading）研究项目。项目从历史成分股、价格、行业和指数权重数据出发，使用严格的 walk-forward 样本外回测，比较两种配对选择方法：

- **Robust Cointegration（严格协整法）**
- **Stable Distance（稳定距离法）**

项目的目标不是展示一条“看起来很赚钱”的曲线，而是回答一个更实际的问题：

> 在避免幸存者偏差、控制统计假阳性、加入交易成本并严格区分训练期与交易期之后，配对交易是否仍然具有可重复、可解释、可用于现实交易的优势？

最终结论是：**改进后的模型能够显著降低市场暴露和回撤，但收益仍然较弱，且对交易成本和市场阶段较敏感，因此目前更适合作为研究基线和分散化策略，而不是可以直接实盘的稳定盈利模型。**

> 本项目用于学术研究和教学，不构成投资建议。

<p align="center">
  <img src="results/strategy_comparison.png" alt="四个 walk-forward 策略的净收益、Sharpe 比率与最大回撤" width="100%">
</p>

<p align="center"><em>图 1：加入基准交易成本后的 walk-forward 净结果。较低的市场暴露并不自动代表较强的经济收益。</em></p>

---

## 目录

- [1. 一分钟了解这个项目](#1-一分钟了解这个项目)
- [2. 项目目的](#2-项目目的)
- [3. 项目使用的数据](#3-项目使用的数据)
- [4. 零基础需要了解的金融知识](#4-零基础需要了解的金融知识)
- [5. 为什么原始策略表现不好](#5-为什么原始策略表现不好)
- [6. 完整研究流程](#6-完整研究流程)
- [7. 本项目采用的方法](#7-本项目采用的方法)
- [8. 交易与组合规则](#8-交易与组合规则)
- [9. 结果与解释](#9-结果与解释)
- [10. 修改参数会不会更好](#10-修改参数会不会更好)
- [11. 这个方法是否可行](#11-这个方法是否可行)
- [12. 下一步改进路线](#12-下一步改进路线)
- [13. 项目结构](#13-项目结构)
- [14. 如何运行项目](#14-如何运行项目)
- [15. 数据发布与许可说明](#15-数据发布与许可说明)
- [16. 参考文献](#17-参考文献)

---

## 1. 一分钟了解这个项目

假设两家业务相似的公司长期价格关系比较稳定，例如其中一只通常约等于另一只经过某个比例调整后的价格。

当两只股票短期偏离时，配对交易会：

- 买入相对便宜的一只；
- 做空相对昂贵的一只；
- 等待两者的价格关系恢复；
- 平掉多头和空头仓位，赚取相对价格变化。

这种策略关心的是“两只股票之间的相对关系”，而不是预测整个市场上涨还是下跌。因此它通常希望做到 **market neutral（市场中性）**。

本项目没有只挑选今天仍在指数里的公司，而是利用历史指数权重重建当时的成分股；每次只使用交易日期之前的数据寻找配对，再在之后的 26 周测试。这比把完整历史数据一次性拿来挑选“最好结果”更接近真实研究流程。

```mermaid
flowchart LR
    A[原始 Bloomberg Excel] --> B[提取和清洗]
    B --> C[重建历史成分股]
    C --> D[156 周形成期]
    D --> E[其中最后 52 周做内部验证]
    E --> F[选择稳定配对]
    F --> G[未来 26 周样本外交易]
    G --> H[收益、成本和风险分析]
    H --> D
```

---

## 2. 项目目的

本项目希望回答以下问题：

1. 原始 S&P 500 配对交易策略为什么亏损？
2. 相关性和协整能否真正找到未来仍然稳定的股票关系？
3. 多重统计检验是否会选出大量偶然显著的“假配对”？
4. 加入内部验证期、稳定性过滤和更合理的止损规则后，结果是否改善？
5. 同一种方法能否同时适用于美国 S&P 500 和欧洲 STOXX 600？
6. 交易成本会消耗多少费前收益？
7. 参数改变后的好结果是真改善，还是回测过拟合？
8. 当前模型是否足以用于真实交易？

项目强调四个原则：

- **可复现**：代码、参数、结果和图表能够重新生成；
- **样本外**：模型只能使用每个交易窗口之前的信息；
- **可解释**：每个过滤条件和交易规则都有明确含义；
- **诚实评价**：弱结果和负结果也保留，不通过事后调参隐藏问题。

---

## 3. 项目使用的数据

项目使用课程提供的 Bloomberg 历史工作簿：

| 市场 | 历史证券数量 | 日频样本 | 第一个交易窗口 |
|---|---:|---|---|
| S&P 500 | 1,355 | 1990-01 至 2018-11 | 1993-01 |
| STOXX 600 | 1,255 | 2002-01 至 2018-11 | 2004-12 |

数据包括：

- 股票日收盘价；
- 历史指数权重；
- 行业分类；
- 股票名称；
- 指数价格；
- STOXX 股票的 Bloomberg 交易所代码。

### 为什么历史成分股很重要

如果只使用今天仍在 S&P 500 或 STOXX 600 中的股票，就会排除历史上退市、被收购或经营失败的公司，从而使历史结果看起来过于优秀。这叫作 **survivorship bias（幸存者偏差）**。

本项目使用每个时点最新可获得的月度指数权重：权重大于 0 的股票才被视为当时的指数成员。

### 数据提取

原始 `.xlsm` 文件体积较大。`pairs_trading/extract.py` 直接读取 Excel 内部 XML，将需要的数据转成 Parquet 和 CSV 缓存，并完成：

- Excel 日期转换；
- 日频、月频和周频数据生成；
- 周五收盘价重采样；
- 历史指数权重整理；
- S&P 行业标签错位修复；
- STOXX 行业和交易所代码提取。

原始数据和缓存默认放在：

```text
data/raw/
data/cache/
```

这两个目录已经写入 `.gitignore`，不会被正常的 `git add .` 上传。

---

## 4. 零基础需要了解的金融知识

### 4.1 多头和空头

- **Long（多头）**：买入股票，价格上涨时获利；
- **Short（空头）**：借入股票卖出，之后低价买回，价格下跌时获利。

配对交易同时持有一只多头和一只空头，希望两者的相对价格恢复，而不是依赖市场整体方向。

### 4.2 市场中性

如果市场整体上涨，多头可能盈利、空头可能亏损；市场下跌时则相反。合理配比两边仓位可以减少市场方向的影响。

但“市场中性”不等于“不会亏钱”。如果两只股票的关系继续扩大而没有恢复，多头和空头组合仍然会亏损。

### 4.3 收益率和对数价格

普通收益率为：

$$
return_t = price_t / price_(t-1) - 1
$$

本项目用对数价格估计配对关系：

$$
log(y_t) = \alpha + \beta \cdot log(x_t) + spread_t
$$

其中：

- `y` 和 `x` 是两只股票；
- `α` 是截距；
- `β` 是 hedge ratio（对冲比率）；
- `spread` 是两只股票经过比例调整后的相对价格偏离。

### 4.4 相关性与协整

**Correlation（相关性）**表示两只股票的短期收益是否经常同方向变化。高相关并不保证两只股票的价格差距不会长期扩大。

**Cointegration（协整）**要求更强：虽然两只价格序列本身可能不断上升或下降，但它们的某个线性组合应当相对稳定，并有回到长期均值的倾向。

因此：

- 相关性适合做候选预筛选；
- 协整更接近配对交易真正需要的长期关系；
- 即使历史上协整，未来仍可能失效。

### 4.5 Spread 和 hedge ratio

价差定义为：

$$
spread_t = log(y_t) - \alpha - \beta \cdot log(x_t)
$$

`β` 决定空头腿相对于多头腿的规模。项目将两边按 `β` 调整后再进行多空交易，避免简单地“一股对一股”。

### 4.6 Mean reversion 和 Z-score

**Mean reversion（均值回归）**是指价差偏离历史平均值后，未来可能回到平均水平。

Z-score 把当前偏离转换为标准差单位：

$$
z_t = \frac{(spread_t - spread_{\mu})}{spread_{\sigma}} 
$$

例如 `z = 2` 表示价差比历史平均值高两个标准差。

### 4.7 Half-life

**Half-life（半衰期）**估计一次价差偏离消失一半大约需要多少周。

- 半衰期太长：可能来不及在交易窗口内恢复；
- 半衰期太短：可能只是噪声或数据异常；
- 本项目只接受 1 至 26 周的半衰期。

### 4.8 P-value、Q-value 与多重检验

P-value 用于衡量单个协整检验的统计显著性。但是当每个窗口测试数千个配对时，即使所有关系都是假的，也会偶然出现一些很小的 p-value。

本项目使用 Benjamini-Hochberg False Discovery Rate 控制，将大量 p-value 转换为 q-value，降低从大量候选中挑到偶然显著配对的风险。

### 4.9 样本内、样本外与 walk-forward

- **In-sample**：用于估计模型和选择参数的数据；
- **Out-of-sample**：模型没有见过、只用于评价的数据；
- **Walk-forward**：随着时间向前推进，每次只使用当时已经存在的数据重新训练，再测试下一段未来数据。

Walk-forward 不能消除所有过拟合，但比在完整历史样本上一次性调参更可信。

### 4.10 评价指标

- **Total return**：整个测试期累计收益；
- **CAGR**：年化复合增长率；
- **Volatility**：收益波动程度；
- **Sharpe ratio**：每单位波动对应的平均收益，本项目按课程口径使用零无风险利率；
- **Sortino ratio**：只使用下行波动衡量风险；
- **Maximum drawdown**：从历史净值高点到之后低点的最大跌幅；
- **Market beta**：策略对指数涨跌的敏感程度；
- **Transaction cost**：开仓、调仓和平仓产生的成本。

---

## 5. 为什么原始策略表现不好

原始 S&P 500 notebook 的结果约为：

- 净累计收益：**-7.23%**；
- 净 Sharpe：**-0.18**；
- 最大回撤：**-13.55%**。

主要问题不是单纯“参数不好”，而是研究设计存在以下风险：

1. **双向检验偏差**：对同一配对做两个方向的 Engle-Granger 检验，再直接取更小 p-value，会提高假阳性概率；
2. **没有控制多重检验**：每个窗口从大量组合中挑最小 p-value，容易选中偶然关系；
3. **缺少独立稳定性检查**：形成期整体看起来协整，不代表形成期末尾仍然稳定；
4. **极端价差仍可能开仓**：旧逻辑可能在价差已经超过止损阈值时开新仓；
5. **成本侵蚀**：部分费前优势在频繁交易后消失；
6. **关系失效**：公司基本面变化、并购、危机和行业结构变化都可能破坏历史关系。

因此，改进重点不是寻找一个让历史曲线最好看的参数，而是减少错误配对和不合理交易。

---

## 6. 完整研究流程

### 第一步：清洗并转换数据

将原始 Excel 转换为更适合分析的 Parquet 和 CSV，并统一日期、ticker、行业和权重格式。

### 第二步：重建历史股票池

在每个形成期结束日，读取当时最新的月度指数权重，只保留权重大于 0 的历史成分股。

### 第三步：过滤不可交易数据

股票必须满足：

- 形成期数据完整；
- 价格高于最低价格限制；
- 周收益没有超过异常波动阈值；
- 有行业和市场分组信息；
- 在当时属于指数成分股。

### 第四步：建立 walk-forward 窗口

每个循环使用：

| 阶段 | 长度 | 用途 |
|---|---:|---|
| Formation | 156 周 | 估计配对关系 |
| Internal validation | 形成期最后 52 周 | 检查关系是否仍然稳定 |
| Trading | 未来 26 周 | 完全样本外交易 |

协整法实际先在前 104 周寻找关系，再用后 52 周检查稳定性；通过后才用完整 156 周重新拟合并冻结参数。

### 第五步：生成候选配对

- 两只股票必须属于同一行业；
- STOXX 还要求具有相同 Bloomberg 交易所代码；
- 周收益相关性必须高于最低阈值；
- 再进入协整或距离筛选。

### 第六步：验证稳定性

检查：

- 验证期均值漂移是否过大；
- 验证期波动是否显著扩大；
- 价差是否至少穿越均值一次；
- 最大标准化偏离是否异常；
- 半衰期是否在 1 至 26 周之间。

### 第七步：选择最终配对

- 最多选择 20 对；
- 同一只股票不能在同一窗口重复出现；
- 没有选满的配对槽位保持现金；
- 所有参数在交易窗口开始前冻结。

### 第八步：交易未来 26 周

根据冻结的价差均值、波动率和 hedge ratio 产生 z-score，执行开仓、止盈、止损和超时退出。

### 第九步：计算组合收益

每个配对最多占组合资金的 `1 / 20`，配对收益相加后除以 20，并扣除交易成本。

### 第十步：保存结果

每个市场和方法都会保存：

- `weekly_returns.csv`：周度费前、费后和指数收益；
- `metrics.csv`：收益与风险指标；
- `selected_pairs.csv`：每个窗口选中的配对和诊断信息；
- `equity_curve.png`：用于 notebook 和 GitHub 的结果图。

---

## 7. 本项目采用的方法

### 7.1 Robust Cointegration

严格协整法主要用于 S&P 500：

1. 在相同行业内按周收益相关性预筛选；
2. 对两个回归方向分别进行 Engle-Granger 检验；
3. 对双向检验进行修正；
4. 在每个行业和市场候选组内进行 Benjamini-Hochberg FDR 控制；
5. 在独立验证期检查均值漂移、波动扩张和均值穿越；
6. 使用完整形成期重新估计 `alpha`、`beta`、spread 均值和标准差；
7. 按稳定性得分选择不重复股票的配对。

这种方法的优点是统计逻辑更严格，缺点是可能拒绝大量配对并长期持有现金。

### 7.2 Stable Distance

稳定距离法主要用于 STOXX 600：

1. 将两只股票的训练期对数价格从同一起点标准化；
2. 计算两条标准化路径之间的平均平方距离；
3. 距离越小，说明历史相对走势越接近；
4. 再估计 OLS hedge ratio；
5. 使用与协整法相同的验证期稳定性和半衰期过滤；
6. 按距离和稳定性选择最终配对。

距离法不依赖“从大量 p-value 中选最小值”，结构更简单，但历史路径接近不代表未来一定均值回归。

### 7.3 为什么两个市场使用不同的最终方法

研究结果表明，没有一种配对选择方法在两个市场都稳定有效：

- S&P 500 上，严格协整法优于距离法；
- STOXX 600 上，稳定距离法明显优于协整法。

这可能与市场结构、行业构成、交易所分组、货币和样本长度有关，也说明不能直接把一个市场上有效的模型复制到另一个市场。

---

## 8. 交易与组合规则

| 参数 | 基准值 | 含义 |
|---|---:|---|
| Formation | 156 周 | 形成期 |
| Validation | 52 周 | 形成期内部验证 |
| Trading | 26 周 | 样本外交易期 |
| Entry | `|z| >= 2.0` | 开仓阈值 |
| Exit | `|z| <= 0.5` | 均值回归退出 |
| Stop | `|z| >= 3.5` | 止损阈值 |
| Maximum holding | 12 周 | 超时退出 |
| Maximum pairs | 20 | 最大配对数量 |
| Transaction cost | 10 bps | 每单位换手成本 |

具体规则：

- `z <= -2`：做多价差，即做多 `y`、做空经过 beta 调整的 `x`；
- `z >= +2`：做空价差；
- `|z| <= 0.5`：认为价差已经接近均值，平仓；
- `|z| >= 3.5`：止损，并在当前半年窗口内锁定该配对；
- 持仓达到 12 周：无论是否回归都退出；
- 如果观察到的价差一开始已经超过止损线，不再开新仓。

---

## 9. 结果与解释

所有策略结果均为周频，使用零无风险利率，并扣除基准交易成本。

| 市场 | 方法 | 累计收益 | CAGR | 年化波动 | Sharpe | 最大回撤 | 市场 beta |
|---|---|---:|---:|---:|---:|---:|---:|
| S&P 500 | **严格协整** | **+1.19%** | +0.05% | 0.55% | **0.09** | **-2.12%** | -0.002 |
| S&P 500 | 稳定距离 | -0.18% | -0.01% | 1.24% | 0.00 | -5.73% | 0.008 |
| S&P 500 | 买入持有 | +498.62% | +7.12% | 16.41% | 0.50 | -56.24% | 1.000 |
| STOXX 600 | 严格协整 | -9.92% | -0.74% | 0.97% | -0.76 | -10.91% | 0.006 |
| STOXX 600 | **稳定距离** | **+2.96%** | +0.21% | 1.48% | **0.15** | **-3.43%** | 0.008 |
| STOXX 600 | 买入持有 | +42.28% | +2.55% | 18.29% | 0.23 | -60.15% | 1.000 |

### S&P 500 结果

严格协整模型将原始策略的负收益改善为小幅正收益，并显著降低回撤。但需要注意：

- 52 个半年窗口共选择 145 个配对实例；
- 平均每个窗口只有 2.8 对；
- 14 个窗口完全没有合格配对；
- 只有约 39% 的周出现策略收益或交易成本；
- 费前累计收益约 +2.52%，费后只剩 +1.19%；
- 前半样本约赚 +1.11%，后半样本只有约 +0.08%。

因此，低风险部分来自严格过滤和大量持有现金，而不是模型持续准确预测均值回归。

<p align="center">
  <img src="results/spx_cointegration/equity_curve.png" alt="S&P 500 严格协整策略权益曲线、策略净值与回撤" width="100%">
</p>

<p align="center"><em>图 2：S&P 500 严格协整策略，包括基准比较、费前与费后净值以及回撤。</em></p>

### STOXX 600 结果

稳定距离模型是本项目表现最好的策略版本，但收益仍然较低：

- 28 个半年窗口每次都选满 20 对；
- 策略几乎每周都有持仓；
- 费前累计收益约 +8.89%，费后只剩 +2.96%；
- 交易成本消耗约三分之二的费前收益；
- 前半样本约亏 -0.62%，后半样本约赚 +3.60%。

它的 beta 和回撤明显低于指数，说明可能具有分散化价值，但结果不够强，不能替代长期股票投资。

<p align="center">
  <img src="results/stoxx_distance/equity_curve.png" alt="STOXX 600 稳定距离策略权益曲线、策略净值与回撤" width="100%">
</p>

<p align="center"><em>图 3：STOXX 600 稳定距离策略，包括基准比较、费前与费后净值以及回撤。</em></p>

### 如何正确理解与指数的比较

指数是长期净多头投资，而配对交易是低 beta 的多空策略，两者承担的风险不同。指数收益更高不自动证明配对交易无价值，但当前策略的 Sharpe 和 CAGR 仍然太低，尚不足以补偿借券、融资、执行和模型失效风险。

---

## 10. 修改参数会不会更好

会让某段历史结果变好，但不代表未来会更好。

在保持历史选对结果不变、只改变一个交易规则的敏感性测试中：

| 市场 | 场景 | 累计收益 | Sharpe | 最大回撤 |
|---|---|---:|---:|---:|
| S&P | 基准 entry 2.0 | +1.19% | 0.09 | -2.12% |
| S&P | entry 1.5 | +5.26% | 0.28 | -2.27% |
| S&P | entry 2.5 | +0.27% | 0.03 | -2.49% |
| S&P | 成本 20 bps | -0.13% | -0.01 | -2.27% |
| STOXX | 基准 entry 2.0 | +2.96% | 0.15 | -3.43% |
| STOXX | entry 1.5 | +8.42% | 0.34 | -2.69% |
| STOXX | entry 2.5 | -0.34% | -0.02 | -3.85% |
| STOXX | 成本 20 bps | -2.65% | -0.12 | -5.20% |

`entry = 1.5` 在两个历史样本中都更好，但这个发现是在看完完整结果后得到的。如果直接把它称为“最佳参数”，就会产生 **backtest overfitting（回测过拟合）**。

正确做法是 nested walk-forward：

1. 只在每个形成期内部比较预先定义的少量参数；
2. 在形成期内选择参数；
3. 冻结参数；
4. 只在下一段 26 周评价一次；
5. 最终汇总所有从未参与参数选择的交易窗口。

参数选择应寻找“附近参数都合理”的稳定区域，而不是寻找一个孤立的历史最高 Sharpe。

---

## 11. 这个方法是否可行

### 作为学术研究：可行

项目已经具备：

- 历史成分股和较低幸存者偏差；
- walk-forward 样本外结构；
- 内部验证期；
- 多重检验控制；
- 明确交易规则；
- 交易成本；
- 两个市场的平行比较；
- 可复用代码、测试、结果和图表。

### 作为分散化策略：有一定可能

两个最终策略的市场 beta 都接近 0，最大回撤远小于股票指数。STOXX 距离法可能作为大型投资组合中的小比例相对价值仓位继续研究。

### 作为真实自动交易策略：目前不可行

原因包括：

- 数据在 2018 年结束，不能证明今天仍然有效；
- 方法和参数已经在完整历史结果上进行过比较；
- 没有完整模拟 bid-ask spread 和市场冲击；
- 没有加入借券费和借券可得性；
- 没有完整处理股息、融资和现金抵押收益；
- 周五收盘信号不一定能按同一收盘价成交；
- STOXX 交易所代码只是币种代理，不是证券级币种；
- 行业标签不是严格的 point-in-time 分类；
- 公司行为、并购、退市和停牌仍可能制造虚假关系。

因此，目前最合理的结论是：

> 该项目证明了更严格的过滤和验证可以减少错误交易，并得到低市场暴露的策略；它没有证明当前模型已经具备稳定、可执行的实盘 alpha。

---

## 12. 下一步改进路线

### 优先级 1：冻结基准并取得新数据

- 保留当前参数和结果，作为不可继续事后优化的 baseline；
- 获取 2019 年之后的 point-in-time 成分股和价格；
- 在查看新数据结果之前写下模型规则；
- 将新时期作为真正 untouched holdout。

### 优先级 2：完善交易级记录

下一版应为每笔交易保存：

```text
market, window, pair, entry_date, exit_date, direction,
entry_z, exit_z, holding_weeks, exit_reason,
gross_return, transaction_cost, borrow_cost, net_return
```

这样才能分析盈利是否来自少数极端交易、哪个行业失效最多，以及成本主要发生在哪里。

### 优先级 3：增加真实执行约束

- 使用下一可成交价格；
- 加入 bid-ask spread、滑点和市场冲击；
- 加入借券费、借券可得性和召回风险；
- 加入股息、融资、保证金和现金收益；
- 正确处理拆股、并购、退市与停牌。

### 优先级 4：改善组合风险管理

- 比较固定权重和波动率缩放权重；
- 设置行业、国家和单只股票暴露上限；
- 检查不同配对之间的残差相关性；
- 避免 20 个配对实际暴露于同一个共同风险因子。

### 优先级 5：再考虑更复杂的模型

- 滚动或 Kalman filter hedge ratio；
- 市场波动和流动性 regime filter；
- 行业因子残差配对；
- 只在简单模型基础上进行机器学习扩展。

每个新组件都应该单独进行 ablation test。复杂模型只有在新的未见样本中稳定优于当前 baseline 时才值得保留。

---

## 13. 项目结构

```text
Pairs Trading Project/
├──> README.md
├──> README.zh-CN.md
├──> requirements.txt
├──> .gitignore
├──> pairs_trading/
│   ├──> __init__.py
│   ├──> backtest.py          # Pair selection and backtest engine
│   ├──> extract.py           # Excel extraction and cache creation
│   ├──> plots.py             # Shared GitHub-ready plotting style
│   └──> run.py               # Command-line runner and result export
├──> notebooks/
│   ├──> SP500_Improved.ipynb
│   ├──> STOXX.ipynb
│   └──> legacy/
│       └──> SP500_Original.ipynb
├──> data/
│   ├──> raw/                 # Ignored: original licensed workbooks
│   └──> cache/               # Ignored: generated Parquet/CSV caches
├──> results/
│   ├──> summary.csv
│   ├──> spx_cointegration/
│   ├──> spx_distance/
│   ├──> stoxx_cointegration/
│   └──> stoxx_distance/
├──> docs/
│   ├──> PROJECT_EXPLANATION_CN.md
│   ├──> reference/
│   └──> legacy/
└──> tests/
    └──> test_pairs_trading.py
```

主要入口：

- `notebooks/SP500_Improved.ipynb`：S&P 500 完整研究；
- `notebooks/STOXX.ipynb`：STOXX 600 完整研究；
- `pairs_trading/backtest.py`：核心策略逻辑；
- `docs/PROJECT_EXPLANATION_CN.md`：更详细的中文答辩说明；
- `results/summary.csv`：所有方法的结果汇总。

---

## 14. 如何运行项目

### 14.1 环境要求

- Python 3.11 或兼容版本；
- macOS、Linux 或 Windows；
- 原始工作簿只在重新提取数据时需要。

### 14.2 创建环境

```bash
cd "/Users/linshenhao/Desktop/Financial Market Analytics/Pairs Trading Project"

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Windows PowerShell 激活命令：

```powershell
.venv\Scripts\Activate.ps1
```

### 14.3 放置原始数据

只有在拥有合法数据访问权限时，将工作簿放到：

```text
data/raw/SPX500 Original.xlsm
data/raw/Stoxx 600 Originale.xlsm
```

### 14.4 提取数据

```bash
python -m pairs_trading.extract --market all
```

只提取单个市场：

```bash
python -m pairs_trading.extract --market spx
python -m pairs_trading.extract --market stoxx
```

### 14.5 运行完整回测

```bash
python -m pairs_trading.run --market all --method both
```

协整扫描是最慢的步骤。输出会写入 `results/`。

### 14.6 运行测试

```bash
python -m unittest discover -s tests -v
```

### 14.7 打开 notebook

```bash
jupyter lab
```

Notebook 默认设置：

```python
RECOMPUTE = False
```

这会直接读取已保存结果，打开速度更快。如果需要从缓存重新运行完整回测，将它改为：

```python
RECOMPUTE = True
```

没有原始 Bloomberg 数据的读者仍然可以查看 GitHub 中已经执行过的 notebook、结果 CSV 和图表。

---

## 15. 数据发布与许可说明

### 推荐方案：不要上传原始数据和缓存

本地原始文件约为：

| 文件 | 大小 | 是否建议上传 |
|---|---:|---|
| `SPX500 Original.xlsm` | 123 MB | 否 |
| `Stoxx 600 Originale.xlsm` | 85 MB | 否 |

原因：

1. Bloomberg 或课程提供的数据可能不允许公开再分发；
2. S&P 工作簿超过 GitHub 普通 Git 的 100 MB 单文件硬限制；
3. Parquet 缓存可以从原始数据重新生成；
4. 大型二进制文件会使仓库克隆和历史记录变得很重。

当前 `.gitignore` 已包含：

```gitignore
data/raw/
data/cache/
```

因此推荐公开上传：

- Python 代码；
- notebook；
- README 和自己的说明文档；
- 汇总结果、选中配对和周收益；
- 结果图表；
- 测试。

公开前还应确认 `docs/reference/` 中的课程题目和 `docs/legacy/` 中的文档是否允许公开。如果不确定，先使用 Private 仓库或暂时不提交这些文件。

### 如何确认数据不会上传

在项目目录运行：

```bash
git check-ignore -v data/raw/*
git check-ignore -v data/cache/*
```

如果终端列出这些文件，说明忽略规则已经生效。

不要使用：

```bash
git add -f data/raw
git add -f data/cache
```

`-f` 会强制绕过 `.gitignore`。

### 如果确实拥有公开授权

只有在确认拥有再分发权后，才考虑 Git LFS。普通 Git 会拒绝超过 100 MB 的单个文件。Git LFS 还涉及存储和带宽额度，因此仍不建议用它发布可重新生成的缓存。

官方说明：

- [GitHub repository limits](https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits)
- [About large files on GitHub](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
- [Ignoring files](https://docs.github.com/en/get-started/git-basics/ignoring-files)

---

## 17. 参考文献

- Engle, R. F., & Granger, C. W. J. (1987). *Co-integration and error correction: Representation, estimation, and testing*.
- Gatev, E., Goetzmann, W. N., & Rouwenhorst, K. G. (2006). *Pairs trading: Performance of a relative-value arbitrage rule*.
- Do, B., & Faff, R. (2010). *Does simple pairs trading still work?*
- Vidyamurthy, G. (2004). *Pairs Trading: Quantitative Methods and Analysis*.

---

## 最终总结

本项目的价值不在于声称“找到了一定赚钱的策略”，而在于展示了一个更可信的量化研究过程：

- 使用历史成分股减少幸存者偏差；
- 用 walk-forward 避免直接使用未来信息；
- 用内部验证和 FDR 减少错误配对；
- 同时研究美国和欧洲市场；
- 计入交易成本并分析其侵蚀；
- 保留负结果、弱结果和真实局限；
- 为下一阶段研究提供清晰、可验证的 baseline。

S&P 500 严格协整法主要通过拒绝不稳定交易降低亏损；STOXX 600 稳定距离法具有一定低 beta 分散化价值，但大部分费前优势被成本消耗。下一步最重要的不是继续优化旧样本，而是在冻结当前规则后，使用更新的未见数据和更真实的执行模型重新检验。

## Authors

| Author | Links |
|---|---|
| **Shen Hao Stefano Lin** | <a href="https://github.com/linshenhao"><img src="https://img.shields.io/badge/GitHub-181717?logo=github&logoColor=white" alt="GitHub"></a> <a href="https://www.linkedin.com/in/linshenhao-49b127393"><img src="https://img.shields.io/badge/LinkedIn-0A66C2?logo=linkedin&logoColor=white" alt="LinkedIn"></a> |
| **Li Hao** | Co-author |

---

<div align="center">

<p><strong>Built as a reproducible deep-learning study of human action recognition on HMDB51.</strong></p>

<p><a href="https://github.com/linshenhao/hmdb51-action-recognition">View the repository</a> · <a href="PROJECT_EXPLANATION.md">Read the detailed walkthrough</a></p>

</div>
