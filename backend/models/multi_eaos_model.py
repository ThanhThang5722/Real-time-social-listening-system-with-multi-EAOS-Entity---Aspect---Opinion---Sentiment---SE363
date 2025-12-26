import torch
import torch.nn as nn
from transformers import AutoModel


class MultiEAOSModel(nn.Module):
    """
    Multi-EAOS Model for Vietnamese Comment Analysis
    Extracts Entity-Aspect-Opinion-Sentiment quadruples from text
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

        # 2. Transformer Encoder Layer
        self.transformer = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(
                d_model=self.bert_hidden_size,
                nhead=4,
                dim_feedforward=hidden_dim,
            ),
            num_layers=2
        )

        # 3. Learnable Queries & Attention
        self.quad_queries = nn.Parameter(torch.randn(max_quads, self.bert_hidden_size))

        # Multi-Head Attention
        self.attention = nn.MultiheadAttention(
            embed_dim=self.bert_hidden_size,
            num_heads=4,
            batch_first=True
        )

        # 4. Prediction Heads (6 outputs per quad)
        # Pointer Network for positions
        self.fc_e_start = nn.Linear(self.bert_hidden_size, max_len)
        self.fc_e_end = nn.Linear(self.bert_hidden_size, max_len)
        self.fc_o_start = nn.Linear(self.bert_hidden_size, max_len)
        self.fc_o_end = nn.Linear(self.bert_hidden_size, max_len)

        # Classification heads
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
        # 1. Position predictions
        e_start_logits = self.fc_e_start(attn_out)
        e_end_logits = self.fc_e_end(attn_out)
        o_start_logits = self.fc_o_start(attn_out)
        o_end_logits = self.fc_o_end(attn_out)

        # 2. Classification predictions
        aspect_logits = self.fc_aspect(attn_out)
        sentiment_logits = self.fc_sentiment(attn_out)

        return {
            "e_start": e_start_logits,
            "e_end": e_end_logits,
            "o_start": o_start_logits,
            "o_end": o_end_logits,
            "aspect": aspect_logits,
            "sentiment": sentiment_logits
        }
