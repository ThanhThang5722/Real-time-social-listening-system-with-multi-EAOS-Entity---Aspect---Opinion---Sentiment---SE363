"""
Multi-EAOS Model - Complete module for production
Extracted from multi-eaos.ipynb

Usage:
    from ml.eaos_model import load_model, EAOSInference

    # Load model
    model, tokenizer, config = load_model("./models/best_model")

    # Inference
    inference = EAOSInference(model, tokenizer, config)
    predictions = inference.predict("Chương trình rất hay!")
"""

import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer
import json
import os
from typing import List, Dict, Any, Tuple


# ============================================================================
# LABEL MAPPINGS (from notebook)
# ============================================================================

ASPECT_MAP = {
    "Địa điểm": 1,
    "Kịch bản": 2,
    "Dàn dựng": 3,
    "Dàn cast": 4,
    "Khách mời": 5,
    "Khả năng chơi trò chơi": 6,
    "Quảng cáo": 7,
    "Thử thách": 8,
    "Tương tác giữa các thành viên": 9,
    "Tinh thần đồng đội": 10,
    "Khác": 0
}

SENTIMENT_MAP = {
    "tích cực": 1,
    "tiêu cực": 2,
    "trung tính": 0,
}


# ============================================================================
# MODEL ARCHITECTURE (from notebook)
# ============================================================================

class MultiEAOSModel(nn.Module):
    """
    Multi-EAOS Model: PhoBERT + Transformer + Attention

    Predicts multiple EAOS quadruples:
    - Entity (start, end)
    - Aspect (classification)
    - Opinion (start, end)
    - Sentiment (classification)
    """

    def __init__(
        self,
        model_name="vinai/phobert-base",
        num_aspects=11,
        num_sentiments=3,
        max_len=256,
        max_quads=4,
        hidden_dim=256
    ):
        super(MultiEAOSModel, self).__init__()

        # 1. BERT Encoder (PhoBERT)
        self.bert = AutoModel.from_pretrained(model_name)
        self.bert_hidden_size = self.bert.config.hidden_size  # 768

        # 2. Transformer Encoder Layer (replaces BiLSTM)
        self.transformer = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model=self.bert_hidden_size,
                nhead=4,
                dim_feedforward=hidden_dim,
            ),
            num_layers=2
        )

        # 3. Learnable Queries for multi-quad prediction
        self.quad_queries = nn.Parameter(torch.randn(max_quads, self.bert_hidden_size))

        # 4. Multi-Head Attention
        self.attention = nn.MultiheadAttention(
            embed_dim=self.bert_hidden_size,
            num_heads=4,
            batch_first=True
        )

        # 5. Prediction Heads (6 outputs per quad)
        self.fc_e_start = nn.Linear(self.bert_hidden_size, max_len)
        self.fc_e_end = nn.Linear(self.bert_hidden_size, max_len)
        self.fc_o_start = nn.Linear(self.bert_hidden_size, max_len)
        self.fc_o_end = nn.Linear(self.bert_hidden_size, max_len)
        self.fc_aspect = nn.Linear(self.bert_hidden_size, num_aspects)
        self.fc_sentiment = nn.Linear(self.bert_hidden_size, num_sentiments)

    def forward(self, input_ids, attention_mask):
        # --- A. Encoding Phase ---
        bert_out = self.bert(input_ids=input_ids, attention_mask=attention_mask)[0]

        # --- B. Transformer Encoder ---
        transformer_out = self.transformer(bert_out)

        # --- C. Multi-EAOS Decoding Phase ---
        batch_size = input_ids.size(0)

        # Expand queries for batch
        queries = self.quad_queries.unsqueeze(0).expand(batch_size, -1, -1)

        # Attention: queries extract quad information
        attn_out, _ = self.attention(
            query=queries,
            key=transformer_out,
            value=transformer_out
        )

        # --- D. Prediction Phase ---
        return {
            "e_start": self.fc_e_start(attn_out),
            "e_end": self.fc_e_end(attn_out),
            "o_start": self.fc_o_start(attn_out),
            "o_end": self.fc_o_end(attn_out),
            "aspect": self.fc_aspect(attn_out),
            "sentiment": self.fc_sentiment(attn_out)
        }


# ============================================================================
# MODEL LOADING
# ============================================================================

def load_model(
    model_dir: str,
    device: torch.device = None
) -> Tuple[MultiEAOSModel, AutoTokenizer, Dict]:
    """
    Load trained model from directory

    Args:
        model_dir: Directory containing latest_checkpoint.pth and config.json
        device: torch device (auto-detected if None)

    Returns:
        (model, tokenizer, config)
    """
    if device is None:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    # Load config
    config_path = os.path.join(model_dir, "config.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config not found: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(config['model_name'], use_fast=True)

    # Create model
    model = MultiEAOSModel(
        model_name=config['model_name'],
        num_aspects=config['num_aspects'],
        num_sentiments=config['num_sentiments'],
        max_len=config['max_len'],
        max_quads=config['max_quads'],
        hidden_dim=config['hidden_dim']
    ).to(device)

    # Load weights from checkpoint
    checkpoint_path = os.path.join(model_dir, "latest_checkpoint.pth")
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    checkpoint = torch.load(checkpoint_path, map_location=device)

    # Extract model state dict from checkpoint
    if 'model_state_dict' in checkpoint:
        model_state_dict = checkpoint['model_state_dict']
    else:
        model_state_dict = checkpoint

    # Load weights (strict=False to ignore missing keys)
    model.load_state_dict(model_state_dict, strict=False)
    model.eval()

    print(f"✅ Model loaded from {model_dir}")
    print(f"   Device: {device}")
    print(f"   Epoch: {config.get('best_epoch', 'N/A')}")
    print(f"   Checkpoint: latest_checkpoint.pth")

    return model, tokenizer, config


# ============================================================================
# INFERENCE CLASS
# ============================================================================

class EAOSInference:
    """Production-ready inference for EAOS predictions"""

    def __init__(
        self,
        model: MultiEAOSModel,
        tokenizer: AutoTokenizer,
        config: Dict,
        confidence_threshold: float = 0.5
    ):
        self.model = model
        self.tokenizer = tokenizer
        self.config = config
        self.confidence_threshold = confidence_threshold
        self.device = next(model.parameters()).device

        # Create reverse mappings
        self.id2aspect = {v: k for k, v in config.get('aspect_map', ASPECT_MAP).items()}
        self.id2sentiment = {v: k for k, v in config.get('sentiment_map', SENTIMENT_MAP).items()}

    def predict(self, text: str, confidence_threshold: float = None) -> List[Dict[str, Any]]:
        """
        Predict EAOS quadruples from text

        Returns:
            [
                {
                    "entity": str,
                    "aspect": str,
                    "opinion": str,
                    "sentiment": str,
                    "confidence": float
                },
                ...
            ]
        """
        threshold = confidence_threshold if confidence_threshold is not None else self.confidence_threshold

        # Tokenize
        inputs = self.tokenizer(
            text,
            padding='max_length',
            truncation=True,
            max_length=self.config['max_len'],
            return_tensors="pt"
        )
        input_ids = inputs['input_ids'].to(self.device)
        attention_mask = inputs['attention_mask'].to(self.device)

        # Inference
        self.model.eval()
        with torch.no_grad():
            outputs = self.model(input_ids, attention_mask)

        # Decode
        return self._decode_outputs(outputs, input_ids[0], threshold)

    def predict_batch(self, texts: List[str], confidence_threshold: float = None) -> List[List[Dict]]:
        """Batch prediction"""
        return [self.predict(text, confidence_threshold) for text in texts]

    def _decode_outputs(self, outputs: Dict, input_ids: torch.Tensor, threshold: float) -> List[Dict]:
        """Decode model outputs to predictions"""
        results = []
        tokens = self.tokenizer.convert_ids_to_tokens(input_ids)

        # Get predictions
        pred_e_start = torch.argmax(outputs['e_start'], dim=-1)[0]
        pred_e_end = torch.argmax(outputs['e_end'], dim=-1)[0]
        pred_o_start = torch.argmax(outputs['o_start'], dim=-1)[0]
        pred_o_end = torch.argmax(outputs['o_end'], dim=-1)[0]
        pred_aspect = torch.argmax(outputs['aspect'], dim=-1)[0]
        pred_sent = torch.argmax(outputs['sentiment'], dim=-1)[0]

        # Get confidence scores
        aspect_probs = torch.softmax(outputs['aspect'], dim=-1)[0]
        sent_probs = torch.softmax(outputs['sentiment'], dim=-1)[0]

        for i in range(len(pred_e_start)):
            e_s, e_e = pred_e_start[i].item(), pred_e_end[i].item()
            o_s, o_e = pred_o_start[i].item(), pred_o_end[i].item()

            # Filter invalid
            if e_s > e_e or o_s > o_e or e_s == 0 or e_e == 0:
                continue
            if e_s >= len(tokens) or o_s >= len(tokens):
                continue

            # Get confidence
            aspect_conf = aspect_probs[i][pred_aspect[i]].item()
            sent_conf = sent_probs[i][pred_sent[i]].item()
            avg_confidence = (aspect_conf + sent_conf) / 2

            if avg_confidence < threshold:
                continue

            # Decode text
            entity_text = self.tokenizer.convert_tokens_to_string(
                tokens[e_s:e_e+1]
            ).replace('_', ' ').strip()

            opinion_text = self.tokenizer.convert_tokens_to_string(
                tokens[o_s:o_e+1]
            ).replace('_', ' ').strip()

            # Get labels
            aspect_label = self.id2aspect.get(pred_aspect[i].item(), "Khác")
            sentiment_label = self.id2sentiment.get(pred_sent[i].item(), "trung tính")

            if entity_text and opinion_text:
                results.append({
                    "entity": entity_text,
                    "aspect": aspect_label,
                    "opinion": opinion_text,
                    "sentiment": sentiment_label,
                    "confidence": round(avg_confidence, 3)
                })

        return results


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def create_inference(model_dir: str, confidence_threshold: float = 0.5) -> EAOSInference:
    """
    Quick setup: Load model and create inference instance

    Usage:
        inference = create_inference("./models/best_model")
        result = inference.predict("Chương trình rất hay!")
    """
    model, tokenizer, config = load_model(model_dir)
    return EAOSInference(model, tokenizer, config, confidence_threshold)
