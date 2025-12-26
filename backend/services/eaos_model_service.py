import torch
import json
import os
from pathlib import Path
from typing import List, Dict
from transformers import AutoTokenizer
from models.multi_eaos_model import MultiEAOSModel
from models.schemas import EAOSLabel


class EAOSModelService:
    """
    Production-ready EAOS Model Service
    Handles model loading, inference, and prediction
    """

    def __init__(self, model_dir: str = None, device: str = None):
        """
        Initialize the EAOS model service

        Args:
            model_dir: Directory containing checkpoint and config files
            device: Device to run model on ('cuda' or 'cpu')
        """
        # Set default model directory
        if model_dir is None:
            model_dir = Path(__file__).parent.parent / "models" / "checkpoints"

        self.model_dir = Path(model_dir)
        self.device = device or ('cuda' if torch.cuda.is_available() else 'cpu')

        # Load configuration
        self._load_config()

        # Initialize tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.config['model_name'],
            use_fast=True
        )

        # Initialize and load model
        self._load_model()

        print(f"✅ EAOS Model loaded successfully")
        print(f"   Device: {self.device}")
        print(f"   Model from epoch: {self.config['best_epoch']}")
        print(f"   Best val_loss: {self.config['best_val_loss']:.4f}")

    def _load_config(self):
        """Load model configuration from config.json"""
        config_path = self.model_dir / "config.json"

        if not config_path.exists():
            raise FileNotFoundError(
                f"Config file not found at {config_path}. "
                "Please ensure config.json is in the model directory."
            )

        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        # Create reverse mappings for labels
        self.id2aspect = {v: k for k, v in self.config['aspect_map'].items()}
        self.id2sentiment = {v: k for k, v in self.config['sentiment_map'].items()}

    def _load_model(self):
        """Load model weights from checkpoint"""
        checkpoint_path = self.model_dir / "latest_checkpoint.pth"

        if not checkpoint_path.exists():
            raise FileNotFoundError(
                f"Checkpoint file not found at {checkpoint_path}. "
                "Please ensure latest_checkpoint.pth is in the model directory."
            )

        # Initialize model
        self.model = MultiEAOSModel(
            model_name=self.config['model_name'],
            num_aspects=self.config['num_aspects'],
            num_sentiments=self.config['num_sentiments'],
            max_len=self.config['max_len'],
            max_quads=self.config['max_quads'],
            hidden_dim=self.config['hidden_dim']
        ).to(self.device)

        # Load checkpoint
        checkpoint = torch.load(checkpoint_path, map_location=self.device)

        # Extract model state dict
        if 'model_state_dict' in checkpoint:
            model_state_dict = checkpoint['model_state_dict']
        else:
            model_state_dict = checkpoint

        # Load weights
        self.model.load_state_dict(model_state_dict, strict=False)
        self.model.eval()

    def predict(self, text: str, confidence_threshold: float = 0.3) -> List[EAOSLabel]:
        """
        Predict EAOS labels from input text

        Args:
            text: Input Vietnamese text
            confidence_threshold: Minimum confidence score (0-1)

        Returns:
            List of EAOSLabel objects
        """
        # Tokenize input
        inputs = self.tokenizer(
            text,
            padding='max_length',
            truncation=True,
            max_length=self.config['max_len'],
            return_tensors="pt"
        )
        input_ids = inputs['input_ids'].to(self.device)
        attention_mask = inputs['attention_mask'].to(self.device)

        # Run inference
        with torch.no_grad():
            outputs = self.model(input_ids, attention_mask)

        # Decode predictions
        results = []
        tokens = self.tokenizer.convert_ids_to_tokens(input_ids[0])

        # Get predictions with argmax
        pred_e_start = torch.argmax(outputs['e_start'], dim=-1)[0]
        pred_e_end = torch.argmax(outputs['e_end'], dim=-1)[0]
        pred_o_start = torch.argmax(outputs['o_start'], dim=-1)[0]
        pred_o_end = torch.argmax(outputs['o_end'], dim=-1)[0]
        pred_aspect = torch.argmax(outputs['aspect'], dim=-1)[0]
        pred_sent = torch.argmax(outputs['sentiment'], dim=-1)[0]

        # Get confidence scores
        aspect_probs = torch.softmax(outputs['aspect'], dim=-1)[0]
        sent_probs = torch.softmax(outputs['sentiment'], dim=-1)[0]

        # Process each quad slot
        for i in range(len(pred_e_start)):
            e_s, e_e = pred_e_start[i].item(), pred_e_end[i].item()
            o_s, o_e = pred_o_start[i].item(), pred_o_end[i].item()

            # Filter invalid predictions
            if e_s > e_e or o_s > o_e:
                continue
            if e_s == 0 or e_e == 0:
                continue
            if e_s >= len(tokens) or o_s >= len(tokens):
                continue

            # Calculate confidence
            aspect_conf = aspect_probs[i][pred_aspect[i]].item()
            sent_conf = sent_probs[i][pred_sent[i]].item()
            avg_confidence = (aspect_conf + sent_conf) / 2

            # Apply confidence threshold
            if avg_confidence < confidence_threshold:
                continue

            # Decode text from tokens
            entity_text = self.tokenizer.convert_tokens_to_string(
                tokens[e_s:e_e+1]
            ).replace('_', ' ').strip()

            opinion_text = self.tokenizer.convert_tokens_to_string(
                tokens[o_s:o_e+1]
            ).replace('_', ' ').strip()

            # Get labels
            aspect_label = self.id2aspect.get(pred_aspect[i].item(), "Khác")
            sentiment_label = self.id2sentiment.get(pred_sent[i].item(), "trung tính")

            # Only add if both entity and opinion are not empty
            if entity_text and opinion_text:
                results.append(EAOSLabel(
                    entity=entity_text,
                    aspect=aspect_label,
                    opinion=opinion_text,
                    sentiment=sentiment_label
                ))

        return results

    def predict_batch(
        self,
        texts: List[str],
        confidence_threshold: float = 0.3
    ) -> List[List[EAOSLabel]]:
        """
        Predict EAOS labels for multiple texts

        Args:
            texts: List of input texts
            confidence_threshold: Minimum confidence score

        Returns:
            List of prediction lists
        """
        return [self.predict(text, confidence_threshold) for text in texts]

    def get_aspect_mapping(self) -> Dict[str, int]:
        """Get aspect label mapping"""
        return self.config['aspect_map']

    def get_sentiment_mapping(self) -> Dict[str, int]:
        """Get sentiment label mapping"""
        return self.config['sentiment_map']
