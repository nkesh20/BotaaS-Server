import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer, PreTrainedModel, AutoConfig

class ToxicRegressor(PreTrainedModel):
    def __init__(self, config):
        super().__init__(config)
        self.num_labels = 1  # Single output for regression
        self.bert = AutoModel.from_config(config)
        self.dropout = nn.Dropout(0.3)
        self.regressor = nn.Linear(config.hidden_size, 1)
        self.post_init()

    def forward(self, input_ids=None, attention_mask=None, labels=None):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        
        # Try pooler_output first, fallback to mean pooling if not available
        pooled_output = getattr(outputs, "pooler_output", None)
        if pooled_output is None:
            pooled_output = outputs.last_hidden_state[:, 0]  # CLS token

        pooled_output = self.dropout(pooled_output)
        logits = self.regressor(pooled_output)
        
        # Apply sigmoid to ensure output is between 0 and 1
        predictions = torch.sigmoid(logits).squeeze(-1)

        loss = None
        if labels is not None:
            # Use MSE loss for regression
            loss_fct = nn.MSELoss()
            loss = loss_fct(predictions, labels)

        return (loss, predictions) if loss is not None else predictions

class ToxicityEstimator:
    def __init__(self, model_name_or_path: str = "chalique/detox-regression", device: str = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.MAX_LENGTH = 256

        # Load config first to pass into custom model
        config = AutoConfig.from_pretrained(model_name_or_path)
        self.model = ToxicRegressor.from_pretrained(model_name_or_path, config=config).to(self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
        self.model.eval()

    def get_toxicity(self, text) -> float:
        encoding = self.tokenizer(
            text,
            truncation=True,
            padding=True,
            max_length=self.MAX_LENGTH,
            return_tensors='pt'
        )
        
        input_ids = encoding['input_ids'].to(self.device)
        attention_mask = encoding['attention_mask'].to(self.device)
        
        with torch.no_grad():
            predictions = self.model(input_ids=input_ids, attention_mask=attention_mask)
            score = predictions.item()
        
        return score
        
    def get_batch_toxicity(self, texts: list[str]) -> list[float]:
        results = []
        for text in texts:
            results.append(self.is_toxic(text))
        return results

# Global instance for easy access
toxicity_estimator = None

def get_toxicity_estimator() -> ToxicityEstimator:
    global toxicity_estimator
    if toxicity_estimator is None:
        toxicity_estimator = ToxicityEstimator()
    return toxicity_estimator