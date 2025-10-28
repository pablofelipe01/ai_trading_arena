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
│   ├── arena_manager.py       # Orchestrates the competition
│   ├── data_fetcher.py         # Binance API + indicator calculation
│   ├── llm_trader.py           # Base class for all LLM traders
│   └── exchange_executor.py   # Paper/live trade execution
├── models/
│   ├── base_model.py           # Abstract LLM trader interface
│   ├── deepseek_trader.py     # The nof1.ai champion
│   ├── gpt_trader.py           # GPT-4 implementation
│   ├── claude_trader.py        # Claude 3 implementation
│   └── llama_trader.py         # Llama 3 (free via Groq)
├── strategies/
│   ├── prompt_templates.py     # nof1-style prompt generation
│   ├── prompts.py              # Prompt management
│   └── risk_management.py      # Position sizing, stop losses
├── utils/
│   ├── logger.py               # Structured logging
│   └── validator.py            # Data validation
├── tests/
│   └── test_*.py               # Comprehensive test suite
├── config/
│   └── config.yaml             # Configuration management
├── data/
│   └── logs/                   # Trading logs and results
├── requirements.txt
├── .env.example
└── main.py
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

```bash
# Activate virtual environment
source venv/bin/activate

# Run paper trading competition
python main.py --mode paper --duration 24h

# Watch the battle unfold!
```

## Development Roadmap

### PHASE 0: Setup ✅ (Current)
- [x] Project structure
- [x] Virtual environment (Python 3.11)
- [x] Dependencies (pandas-ta for TA)
- [x] Environment configuration
- [x] Git repository

### PHASE 1: Foundations (Next)
- [ ] Configuration manager (Pydantic)
- [ ] Logger with colors (Loguru)
- [ ] Data validators
- [ ] Error handling framework
- [ ] Unit tests

### PHASE 2: Prompt System
- [ ] NOF1PromptTemplate (exact replica)
- [ ] Template versioning
- [ ] Variable injection system
- [ ] A/B testing framework

### PHASE 3: Paper Trading
- [ ] Mock exchange (simulates Binance)
- [ ] Portfolio tracker
- [ ] Order execution with slippage
- [ ] Performance metrics

### PHASE 4: Data Pipeline
- [ ] Binance API integration
- [ ] Multi-timeframe data (1m, 3m, 15m, 1h, 4h)
- [ ] Technical indicators (EMA, MACD, RSI, ATR)
- [ ] Oldest → newest formatting
- [ ] Caching and rate limiting

### PHASE 5: LLM Integration
- [ ] 5.1: Base class (AbstractLLMTrader)
- [ ] 5.2: DeepSeek (PRIORITY - the champion)
- [ ] 5.3: Llama via Groq (free baseline)
- [ ] 5.4: GPT-4 and Claude
- [ ] 5.5: Response parsing and validation

### PHASE 6: Arena Manager
- [ ] Competition orchestration
- [ ] Parallel LLM execution
- [ ] Real-time leaderboard
- [ ] Results export

### PHASE 7: Testing
- [ ] End-to-end tests
- [ ] Chaos testing
- [ ] Performance benchmarks
- [ ] Snapshot testing

### PHASE 8: Visualization
- [ ] CLI dashboard (Rich)
- [ ] Equity curves
- [ ] Decision logs
- [ ] Performance reports

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

**Status**: PHASE 0 Complete ✅ | PHASE 1 Starting Soon

**Last Updated**: 2025-10-28

Built with curiosity, tested with rigor, inspired by nof1.ai
