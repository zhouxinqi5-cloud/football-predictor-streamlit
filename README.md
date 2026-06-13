# 个人足球预测分析工具

一个基于 Python 3.10+ 和 Streamlit 的个人足球数据分析网页工具。模型以基本面为主，欧赔、亚盘和大小球为辅助，重点检查基本面与盘口一致性、热门方向过热和欧亚分歧，并给出保守概率。

## 当前功能

- 按日期和联赛自动获取比赛列表，支持世界杯、五大联赛和欧冠。
- 自动比赛使用 Football-Data API；无 Key、接口失败或当日无数据时使用稳定 mock 回退。
- 自动计算近期状态、攻击、防守、主客场修正、14 天疲劳指数和积分压力指数。
- 自动输出主客队基本面分、强度差和 `home/away/even` 倾向。
- 从当日比赛生成 Top 5 分析优先列表，区分强弱差与波动代理。
- 手动输入球队、比赛背景、伤停、战意、欧赔、亚盘和大小球。
- 使用 Football-Data.org v4 API 自动获取赛事球队、赛程、积分榜、近 5 场和进失球。
- 自动数据只用于辅助填充基本面，伤停、战意和赔率仍由用户确认。
- 未配置任何 API Key 时，仍可完全手动生成中文分析报告。
- `odds_fetcher.py` 已预留付费赔率供应商接口，但当前不会自动请求付费服务。

## 本地运行

1. 创建并激活虚拟环境：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS/Linux 使用：

```bash
python -m venv .venv
source .venv/bin/activate
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 可选：复制 `.env.example` 为 `.env` 并填写 Key。不要提交 `.env`：

```dotenv
FOOTBALL_DATA_API_KEY=your_football_data_key
ODDS_API_KEY=
```

4. 启动网页：

```bash
streamlit run app.py
```

5. 命令行样例和测试：

```bash
python football_predictor/main.py
python -m unittest discover -s tests -v
```

## Football-Data API

在 [Football-Data.org](https://www.football-data.org/) 注册免费 Key。程序使用 v4 API，并通过请求头 `X-Auth-Token` 认证。

自动获取时建议使用 API 官方英文球队名，例如 `Arsenal FC`。免费套餐的赛事覆盖和请求频率可能有限；遇到权限、限流或球队匹配错误时，页面会保留手动输入流程。

自动工作流：选择日期和联赛 → 自动获取比赛 → 选择比赛 → 自动生成基本面评分 → 手动检查盘口和其他信息 → 生成分析报告。自动填写后的全部输入仍可手动修改。

## API Key 配置

程序按以下顺序读取配置：

1. 环境变量或本地 `.env`。
2. Streamlit `st.secrets`。

本地也可复制 `.streamlit/secrets.toml.example` 为 `.streamlit/secrets.toml`：

```toml
FOOTBALL_DATA_API_KEY = "your_football_data_key"
ODDS_API_KEY = ""
```

`.env` 和 `.streamlit/secrets.toml` 已加入 `.gitignore`。

## Streamlit Community Cloud 部署

1. 将项目推送到 GitHub，确认根目录包含 `app.py` 和 `requirements.txt`。
2. 在 Streamlit Community Cloud 创建应用，选择仓库、分支，并将入口设为 `app.py`。
3. 在应用的 Advanced settings / Secrets 中添加：

```toml
FOOTBALL_DATA_API_KEY = "your_football_data_key"
ODDS_API_KEY = ""
```

4. 点击 Deploy。不要把真实 Key 写入仓库中的任何文件。

官方说明：[部署应用](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app)｜[Secrets 管理](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)

## Render 部署

仓库已包含 `render.yaml`，可以在 Render 使用 Blueprint 部署；也可以手动创建 Python Web Service：

- Build Command：`pip install -r requirements.txt`
- Start Command：`streamlit run app.py --server.address 0.0.0.0 --server.port $PORT`
- 环境变量：`FOOTBALL_DATA_API_KEY`、`ODDS_API_KEY`

Streamlit 必须监听 Render 提供的 `$PORT`，并绑定到 `0.0.0.0`。部署后若不使用自动数据，`FOOTBALL_DATA_API_KEY` 可以留空。

官方说明：[Render Web Services](https://render.com/docs/web-services)

## 项目结构

```text
app.py                              Streamlit 网页入口
football_predictor/
  analysis_service.py              完整分析流水线
  data_fetcher.py                   Football-Data 免费数据客户端
  fixture_fetcher.py                自动赛程与 mock 回退
  feature_engine.py                 自动基本面特征工程
  match_recommender.py              Top 5 分析优先级
  odds_fetcher.py                   付费赔率接口预留
  fundamental_analyzer.py           基本面分析
  odds_analyzer.py                  欧赔、亚盘和大小球分析
  probability_model.py              保守概率融合
  score_predictor.py                比分与进球区间
  risk_analyzer.py                  风险识别
  report_generator.py               中文报告生成
```

## 免责声明

本项目仅用于足球数据分析、概率研究和学习。盘口仅作为市场情绪与风险参考，不构成投注建议，不提供任何收益承诺，也不保证预测结果准确。伤停、首发、战意、赛制和临场数据均可能导致模型结果失效。
