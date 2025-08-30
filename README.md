# 🛡️ AWS Guardrails Demo Project

This project is an **introduction to AWS Bedrock Guardrails**, showing how to create, manage, and test guardrails for secure and controlled interactions with foundation models.  
It demonstrates the main **features and API usage** for developers starting with Guardrails.

---

## 📂 Project Structure
```
├── bedrock/
│   ├── __init__.py
│   ├── config.py        # Configuration settings (region, API keys, etc.)
│   └── main.py          # Core functions for Guardrail operations
├── .env                 # Environment variables (NOT committed)
├── .gitignore           # Git ignore rules
├── poetry.lock          # Poetry lock file
├── pyproject.toml       # Poetry project configuration
└── README.md            # Documentation
```


---

## 🚀 Getting Started

### **1. Clone the Repository**
```bash
git clone https://github.com/laura19992811/aws-guardrails-demo.git
cd aws-guardrails-demo
```

### **2. Set Up Environment**
Use [Poetry](https://python-poetry.org/) to manage dependencies:
```bash
poetry install
```

Create a `.env` file in the root directory:
```env
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFUALT_REGION=us-east-1
ACCOUNT_ID=your-account-id
```

### **3. Run the Examples**
Activate the environment and run the script:
```bash
poetry run python bedrock/main.py
```

---

## 🛠️ Requirements
- Python 3.9+
- AWS CLI configured or access keys set in `.env`
- Poetry for dependency management

---


## 📚 Resources
- [AWS Bedrock Guardrails Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html)
- [AWS SDK for Python (boto3)](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [Poetry Dependency Manager](https://python-poetry.org/)

