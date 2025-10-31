# AI Trading Arena

> **Where LLMs Battle for Trading Supremacy**

A competitive trading environment where different Large Language Models (LLMs) compete against each other in cryptocurrency trading using real market data and identical prompts. Inspired by [nof1.ai](https://nof1.ai) where DeepSeek achieved **+11.06% returns**, outperforming GPT-4 and Claude.

## Overview

AI Trading Arena is a transparent, open-source project that pits multiple LLMs against each other in crypto trading competitions. Each model receives:
- **Identical market data** (formatted oldest → newest)
- **Same prompt structure** (based on proven nof1.ai format)
- **Equal starting capital** ($100 per model)
- **Identical risk parameters**

The goal: Discover which AI truly has the best trading instincts.

## The Contenders (Tier 1)

| Model | Narrative | API Cost | Status |
|-------|-----------|----------|--------|
| **DeepSeek** | The Champion Defends (+11.06% on nof1.ai) | ~$5-10/month | Priority |
| **Llama 3 70B** | The Open Source Underdog | FREE (via Groq) | Active |
| **GPT-4 Turbo** | The Favorite Seeks Revenge | ~$30-50/month | Active |
| **Claude 3 Sonnet** | The Professional Analyst | ~$20-40/month | Active |

*Tier 2 models (Gemini, Qwen, etc.) coming in future phases*

## Why This Exists

1. **Validate nof1.ai Results**: Can we replicate DeepSeek's success?
2. **Democratize AI Trading Research**: 100% open source, transparent methodology
3. **Educational**: Learn about LLM-driven trading systems
4. **Experimental**: Test different prompt strategies and data formats
5. **Fun**: Watch AIs battle it out in real-time

## nof1.ai Inspiration

This project follows the proven methodology from nof1.ai:

### Data Format (CRITICAL)
```
ALL BTC DATA
Current_price = 115071.5, current_ema20 = 114736.219,
current_macd = 167.364, current_rsi (7 period) = 76.248

Price Series (1 minute, oldest → latest):
Mid prices: [114561.0, 114620.5, 114761.0, ...]
EMA indicators (20-period): [114424.317, 114441.811, ...]
MACD indicators: [7.501, 20.792, 43.174, ...]
RSI indicators (14-Period): [64.261, 65.475, 73.028, ...]
```

**Key Principles**:
- Always **oldest → newest** ordering (LLMs understand temporal sequences this way)
- Multiple timeframes (1m, 3m, 15m, 1h, 4h)
- Raw data arrays (let the AI interpret)
- Technical indicators: EMA, MACD, RSI, ATR
- Market context: funding rates, open interest

## Project Structure

```
ai_trading_arena/
├── core/
│   └── arena_manager.py       # Competition orchestrator
├── data/
│   └── binance_fetcher.py     # Data fetching & caching
├── models/
│   ├── llm_client.py          # LLM integrations (4 providers)
│   ├── llm_manager.py         # Model management
│   └── exchange_executor.py   # Portfolio & trade execution
├── strategies/
│   ├── prompt_builder.py      # NOF1-style prompt generation
│   └── templates/             # Prompt templates
├── utils/
│   ├── config_loader.py       # Configuration management
│   ├── indicators.py          # Technical indicators
│   ├── validator.py           # Decision validation
│   └── errors.py              # Custom exceptions
├── tests/
│   ├── test_chaos.py          # Chaos testing (13 tests)
│   ├── test_performance.py    # Performance benchmarks (9 tests)
│   ├── test_stress.py         # Stress testing (11 tests)
│   ├── extended_runner.py     # 24+ hour competition runner
│   ├── results_analyzer.py    # Results analysis tool
│   └── generate_test_report.py # Test reporting
├── visualization/
│   ├── chart_builder.py       # Plotly chart utilities
│   ├── equity_curves.py       # Equity curve plotter
│   ├── decision_viewer.py     # Decision logs viewer
│   ├── dashboard.py           # Performance dashboard
│   └── html_reporter.py       # HTML report generator
├── web/                       # Real-time Web Dashboard (PHASE 9)
│   ├── app.py                 # FastAPI server with WebSocket
│   └── static/
│       └── index.html         # Live dashboard frontend
├── docs/
│   ├── README.md              # Documentation index
│   ├── COMPLETE_PROJECT_DOCUMENTATION.md  # Full documentation
│   └── PHASE_*_COMPLETE.md    # Individual phase docs
├── config/
│   └── config.yaml            # Main configuration
├── data/                      # Runtime data
│   ├── cache/                 # API response cache
│   ├── logs/                  # Application logs
│   ├── results/               # Competition results
│   ├── checkpoints/           # Session checkpoints
│   └── visualizations/        # Charts & reports
├── requirements.txt           # Python dependencies
├── .env.example              # Environment template
└── main.py                   # CLI entry point
```

## Quick Start

### Prerequisites
- Python 3.11+
- API keys (see `.env.example`)
- Basic understanding of crypto trading

### Installation

```bash
# Clone the repository
git clone git@github.com:pablofelipe01/ai_trading_arena.git
cd ai_trading_arena

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Get API Keys

1. **DeepSeek** (Priority): https://platform.deepseek.com/api_keys
   - Cost: ~$0.14/1M input tokens

2. **Groq (Llama - FREE)**: https://console.groq.com/keys
   - Free tier available

3. **OpenAI**: https://platform.openai.com/api-keys
   - GPT-4 Turbo: ~$10/1M input tokens

4. **Anthropic**: https://console.anthropic.com/settings/keys
   - Claude 3 Sonnet: ~$3/1M input tokens

5. **Binance** (Read-only): https://www.binance.com/en/my/settings/api-management
   - For market data only (no trading permissions needed for paper trading)

### Configuration

Edit `config/config.yaml`:
```yaml
trading:
  mode: "paper"  # ALWAYS start with paper!
  capital_per_model: 100

models:
  deepseek:
    enabled: true  # The nof1.ai champion
  llama:
    enabled: true  # Free baseline
  gpt4:
    enabled: true
  claude:
    enabled: true
```

### Run Your First Competition

#### Option 1: Real-time Web Dashboard (Recommended) 🌐

Watch the competition live in your browser with real-time updates!

```bash
# Activate virtual environment
source venv/bin/activate

# Start the web dashboard
python -m uvicorn web.app:app --host 0.0.0.0 --port 8000

# Open your browser to: http://localhost:8000
```

**Features:**
- 📈 Live equity curves updating every round
- 🏆 Real-time leaderboard with animations
- 🤖 Model decisions and reasoning displayed live
- ⚡ Control panel to start/stop/pause competitions
- 📊 Interactive Plotly charts
- 🔌 WebSocket for instant updates

#### Option 2: CLI Mode

Run headless competitions from the command line:

```bash
# Activate virtual environment
source venv/bin/activate

# Run paper trading competition
python main.py --mode paper --duration 24h

# View results in generated HTML reports
```

## Documentation

📚 **Comprehensive documentation available in [`/docs`](docs/)**

- **[Complete Documentation](docs/COMPLETE_PROJECT_DOCUMENTATION.md)** - Full project guide
- **[Documentation Index](docs/README.md)** - Navigate all docs
- **Phase-by-Phase Guides**:
  - [PHASE 0](docs/PHASE_0_COMPLETE.md) - Project Setup
  - [PHASE 1](docs/PHASE_1_COMPLETE.md) - Configuration & Data
  - [PHASE 2](docs/PHASE_2_COMPLETE.md) - LLM Integration
  - [PHASE 3-5](docs/PHASE_3_4_5_COMPLETE.md) - Trading System
  - [PHASE 6](docs/PHASE_6_COMPLETE.md) - Arena Manager
  - [PHASE 7](docs/PHASE_7_COMPLETE.md) - Testing Suite
  - [PHASE 8](docs/PHASE_8_COMPLETE.md) - Visualization

## Development Status

### ✅ ALL PHASES COMPLETE (0-9)

#### PHASE 0: Project Setup ✅
- [x] Project structure
- [x] Dependencies (30+ packages)
- [x] Environment configuration
- [x] Git repository

#### PHASE 1: Configuration & Data ✅
- [x] Configuration loader (Pydantic)
- [x] Binance integration
- [x] Multi-timeframe data fetching
- [x] Technical indicators (EMA, MACD, RSI, ATR)
- [x] Caching system

#### PHASE 2: LLM Integration ✅
- [x] Base LLM client
- [x] DeepSeek integration
- [x] Groq/Llama integration
- [x] OpenAI GPT-4 integration
- [x] Anthropic Claude integration
- [x] Parallel execution

#### PHASE 3: Prompt Engineering ✅
- [x] NOF1-style prompt templates
- [x] Multi-timeframe formatting
- [x] Indicator integration
- [x] Account state representation

#### PHASE 4: Decision Validation ✅
- [x] Pydantic models
- [x] JSON parsing with error recovery
- [x] Risk validation
- [x] Type-safe validation

#### PHASE 5: Portfolio Management ✅
- [x] Paper trading mode
- [x] Position tracking
- [x] PnL calculation
- [x] Trade execution
- [x] Win rate tracking

#### PHASE 6: Arena Manager ✅
- [x] Competition orchestration
- [x] Multi-round loop
- [x] Real-time leaderboards
- [x] Results export (JSON/CSV)
- [x] CLI interface

#### PHASE 7: Testing ✅
- [x] Chaos testing (13 tests)
- [x] Performance benchmarks (9 tests)
- [x] Stress testing (11 tests)
- [x] Extended competition runner
- [x] Results analyzer
- [x] Test report generator

#### PHASE 8: Visualization ✅
- [x] Interactive Plotly charts
- [x] Equity curves with drawdown
- [x] Decision logs viewer
- [x] Performance dashboards
- [x] HTML report generator

#### PHASE 9: Real-time Web Dashboard ✅
- [x] FastAPI server with WebSocket
- [x] Live equity curves
- [x] Real-time leaderboard
- [x] Competition control panel
- [x] Event broadcasting system
- [x] Interactive Plotly.js charts

## Key Features

### Transparency
- Every decision logged with timestamp
- All prompts saved for reproducibility
- Full audit trail
- Open source methodology

### Safety First
- **Paper trading by default**
- Circuit breakers for losses
- Position size limits
- Emergency stop functionality
- Rate limiting on all APIs

### Prompt Engineering
Multiple template versions:
- `nof1_exact`: Exact replica of nof1.ai format
- `simplified`: Educational version
- `advanced`: With order flow and liquidations
- `minimal`: Baseline for comparison
- `experimental`: Test new ideas

### Fair Competition
- Identical data for all models
- Same decision intervals (3 min)
- Equal starting capital
- Parallel execution (no time advantage)
- Standardized risk parameters

## Technical Details

### Data Format Specification
Following nof1.ai methodology:
- **Temporal Order**: ALWAYS oldest → newest
- **Timeframes**: 1m, 3m (primary), 15m, 1h, 4h
- **Indicators**:
  - EMA (20, 50 periods)
  - MACD (12, 26, 9)
  - RSI (7, 14 periods)
  - ATR (3, 14 periods)
- **Market Data**: Price, volume, funding rate, open interest

### LLM Response Format
Each model must return:
```json
{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0-1.0,
  "reasoning": "Why this decision",
  "position_size": 0.0-1.0,  // Fraction of capital
  "stop_loss": float,
  "take_profit": float
}
```

### Technology Stack
- **Python 3.11**: Modern async support
- **pandas-ta**: Technical analysis (pure Python, no compilation)
- **ccxt**: Exchange API abstraction
- **asyncio**: Parallel LLM calls
- **Pydantic**: Data validation
- **Loguru**: Beautiful logging
- **Rich**: Terminal UI
- **pytest**: Comprehensive testing

## Cost Estimates

### Minimum Setup (DeepSeek + Llama)
- DeepSeek API: ~$5-10/month
- Llama via Groq: **FREE**
- Binance data: Free
- **Total: ~$5-10/month**

### Full Setup (All 4 Models)
- DeepSeek: ~$5-10/month
- Llama: FREE
- GPT-4: ~$30-50/month
- Claude: ~$20-40/month
- **Total: ~$55-100/month**

*Based on ~480 calls/day (every 3 minutes)*

## Safety & Risk Management

### Built-in Protections
- Maximum 2% risk per trade
- 5% daily loss circuit breaker
- 20% max position size
- Emergency stop button
- Rate limiting on all APIs

### Paper Trading Features
- Simulated order execution
- Realistic slippage modeling
- No real money at risk
- Perfect for testing and learning

## Contributing

This is a learning project built step-by-step. Contributions welcome!

### Development Philosophy
1. **Go slow**: Quality over speed
2. **Test everything**: Minimum 80% coverage
3. **Document inline**: Code should be self-explanatory
4. **Ask questions**: Uncertainty is OK
5. **Follow nof1 format**: It's proven to work

### How to Contribute
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Ensure all tests pass
5. Submit a pull request

## References

- [nof1.ai](https://nof1.ai) - Original inspiration
- DeepSeek performance: +11.06% (nof1.ai results)
- Prompt engineering based on proven nof1 methodology

## License

MIT License - See LICENSE file for details

## Disclaimer

**IMPORTANT**:
- This is an **educational project**
- Start with **paper trading only**
- Crypto trading is **high risk**
- Past performance (including nof1.ai results) **does not guarantee future returns**
- Only use money you can afford to lose
- Not financial advice

## Contact

- GitHub Issues: Bug reports and feature requests
- Discussions: Questions and ideas

---

**Status**: ✅ ALL PHASES COMPLETE (0-9) | Production Ready

**Last Updated**: 2025-10-31

**Total Development**: ~22 hours | ~9,000+ lines of code

Built with curiosity, tested with rigor, inspired by nof1.ai 🚀
