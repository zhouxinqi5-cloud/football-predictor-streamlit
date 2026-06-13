# Pro Football Analytics Engine

一个可部署到 Streamlit Cloud 的职业级足球量化分析工具。系统以基本面为主，融合欧赔、亚盘、大小球和市场行为代理，输出保守的胜平负概率、比分分布、风险等级与分析优先级。

## 核心能力

- 自动按日期和联赛读取比赛，优先使用 Football-Data.org 免费 API。
- 默认查询当天比赛，并在页面显示当前查询日期。
- 无 API Key、接口失败或当日无数据时自动使用确定性 mock 数据，同时明确提示“模拟示例数据，不是真实近期比赛”。
- 常见国家队、五大联赛球队和赛事名称优先显示中文；未知英文名会标记“未翻译”。
- 自动构建 Elo-like、最近 10 场、强弱对手修正、攻防、xG 代理、主客场、疲劳、旅行和排名压力特征。
- 解读欧赔概率偏移、返还率、亚盘升降盘与水位组合、大小球预期变化。
- 计算热门拥挤度、市场防守方向、风险对冲、诱盘指标和控盘倾向代理。
- 按基本面 50%、盘口 25%、市场行为 25% 融合概率，并进行冲突与过热收缩。
- 自动模式支持一键分析 Top N；手动模式可输入球队、盘口、战意、伤停记录和比赛背景。
- 不使用网页爬虫，不强制接入付费 API。

“庄家行为”“资金方向”和“诱盘”均是公开赔率结构的计算代理，不代表掌握真实资金流或庄家内部意图。

## 项目结构

```text
app.py                         Streamlit Cloud 入口
football_ai/
  config.py                    数据合同与可调权重
  core/
    match_loader.py            API 优先的自动赛程
    feature_engine.py          职业级基本面评分
    odds_engine.py             欧赔、亚盘、大小球分析
    market_behavior.py         市场行为与诱盘风险代理
    probability_engine.py      概率融合与比分分布
    risk_engine.py             多因素风险模型
    report_engine.py           完整流水线与中文报告
  team_name_mapper.py          球队与赛事中文名称映射
  data/
    api_client.py              Football-Data API 适配器
    mock_data.py               无 Key 离线数据与市场基线
  ui/
    app.py                     Streamlit 专业界面
football_predictor/            旧版模块，保留兼容性
tests/                         单元、部署导入和页面测试
```

## 本地运行

需要 Python 3.10+：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

命令行旧版样例与完整测试：

```powershell
python football_predictor/main.py
python -m unittest discover -s tests -v
```

没有 API Key 时，网页仍可自动加载 mock 比赛、运行完整模型并生成报告。

## API Key

程序先读取环境变量或 `.env`，再读取 Streamlit secrets。复制 `.env.example` 为 `.env`：

```dotenv
FOOTBALL_DATA_API_KEY=
ODDS_API_KEY=
```

Football-Data 免费 Key 可在 [football-data.org](https://www.football-data.org/) 申请。`ODDS_API_KEY` 仅为后续付费赔率接口预留，当前不会强制调用。

Streamlit secrets 格式：

```toml
FOOTBALL_DATA_API_KEY = "your_key"
ODDS_API_KEY = ""
```

不要提交 `.env` 或真实 secrets。

## Streamlit Cloud 部署

1. 将仓库推送到 GitHub，确认根目录存在 `app.py` 和 `requirements.txt`。
2. 在 Streamlit Community Cloud 选择仓库和分支，入口填写 `app.py`。
3. 在 Advanced settings / Secrets 中添加上述 TOML 配置；免费 API Key 也可以留空。
4. 点击 Deploy，日志出现 `RUNNING` 后即可用手机访问公网地址。

文档：[部署应用](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app)｜[Secrets 管理](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)

## Render 部署

仓库包含 `render.yaml`。手动创建服务时使用：

- Build Command：`pip install -r requirements.txt`
- Start Command：`streamlit run app.py --server.address 0.0.0.0 --server.port $PORT`
- 环境变量：`FOOTBALL_DATA_API_KEY`、`ODDS_API_KEY`

## 免责声明

本项目仅用于足球数据分析、概率研究和学习，不构成投注建议，不提供任何收益承诺，也不保证预测准确率。阵容、伤停、战意、赛制和临场数据均可能使模型结果失效。
