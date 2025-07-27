import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer, PreTrainedModel, AutoConfig

# Same class you used during training
class ToxicClassifier(PreTrainedModel):
    def __init__(self, config):
        super().__init__(config)
        self.num_labels = config.num_labels
        self.bert = AutoModel.from_config(config)
        self.dropout = nn.Dropout(0.3)
        self.classifier = nn.Linear(config.hidden_size, config.num_labels)
        self.post_init()

    def forward(self, input_ids=None, attention_mask=None, labels=None):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = getattr(outputs, "pooler_output", None)
        if pooled_output is None:
            pooled_output = outputs.last_hidden_state[:, 0]

        pooled_output = self.dropout(pooled_output)
        logits = self.classifier(pooled_output)

        loss = None
        if labels is not None:
            loss_fct = nn.CrossEntropyLoss()
            loss = loss_fct(logits.view(-1, self.num_labels), labels.view(-1))

        return (loss, logits) if loss is not None else logits

class ToxicityDetector:
    def __init__(self, model_name_or_path: str = "chalique/tox_det", device: str = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        # Load config first to pass into custom model
        config = AutoConfig.from_pretrained(model_name_or_path)
        self.model = ToxicClassifier.from_pretrained(model_name_or_path, config=config).to(self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
        self.model.eval()

    def is_toxic(self, text: str) -> tuple[bool, float]:
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, padding=True).to(self.device)
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs if not isinstance(outputs, tuple) else outputs[1]
            probs = F.softmax(logits, dim=-1)
            confidence = probs[0][1].item()
            predicted_class = bool(torch.argmax(probs, dim=-1).item())
            return predicted_class, confidence

    def batch_is_toxic(self, texts: list[str]) -> list[tuple[bool, float]]:
        results = []
        for text in texts:
            results.append(self.is_toxic(text))
        return results

# Global instance for easy access
toxicity_detector = None

def get_toxicity_detector() -> ToxicityDetector:
    """Get or create the global toxicity detector instance"""
    global toxicity_detector
    if toxicity_detector is None:
        toxicity_detector = ToxicityDetector()
    return toxicity_detector