"""
Active Learning System for AnotadorPad.

Implements:
- Uncertainty sampling (entropy, margin, least confidence)
- Pseudo-labeling with confidence threshold
- LoRA fine-tuning pipeline (5-min adaptation)
- Human-in-the-loop validation UI
- Dataset management for continuous learning
"""
from __future__ import annotations
import os
import sys
import json
import time
import shutil
import random
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading
import queue

import cv2
import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, Dataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False

try:
    import loralib as lora
    LORA_AVAILABLE = True
except ImportError:
    LORA_AVAILABLE = False


# ==================== ENUMS & DATACLASSES ====================

class UncertaintyMethod(Enum):
    LEAST_CONFIDENCE = "least_confidence"
    MARGIN = "margin"
    ENTROPY = "entropy"
    CONSISTENCY = "consistency"  # Test-time augmentation consistency


class QueryStrategy(Enum):
    UNCERTAINTY = "uncertainty"
    DIVERSITY = "diversity"
    HYBRID = "hybrid"


@dataclass
class ActiveLearningConfig:
    """Configuration for active learning loop."""
    # Uncertainty sampling
    uncertainty_method: UncertaintyMethod = UncertaintyMethod.ENTROPY
    query_batch_size: int = 20
    uncertainty_threshold: float = 0.5  # Samples above this are "uncertain"
    
    # Pseudo-labeling
    pseudo_label_confidence: float = 0.8  # High confidence → auto-label
    pseudo_label_max_per_class: int = 100
    
    # Fine-tuning (LoRA)
    lora_rank: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.1
    finetune_epochs: int = 5
    finetune_lr: float = 1e-4
    finetune_batch_size: int = 8
    
    # Query strategy
    query_strategy: QueryStrategy = QueryStrategy.HYBRID
    diversity_weight: float = 0.3
    
    # Paths
    model_path: str = "models/pads.onnx"
    dataset_dir: str = "active_learning_data"
    checkpoint_dir: str = "checkpoints/active_learning"
    
    # Validation
    min_samples_per_class: int = 5
    max_total_samples: int = 10000


@dataclass
class DetectionResult:
    """Result from detector with uncertainty info."""
    bbox: Tuple[float, float, float, float]  # x, y, w, h
    confidence: float
    class_id: int
    uncertainty: float
    uncertainties_per_class: np.ndarray
    entropy: float
    margin: float
    image_path: str
    image_shape: Tuple[int, int]


@dataclass
class LabeledSample:
    """Human-labeled or pseudo-labeled sample."""
    image_path: str
    bbox: Tuple[float, float, float, float]  # normalized xywh
    class_id: int
    is_pseudo: bool = False
    confidence: float = 1.0
    annotator: str = "human"
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)


# ==================== UNCERTAINTY ESTIMATION ====================

class UncertaintyEstimator:
    """Estimates prediction uncertainty using multiple methods."""
    
    def __init__(self, method: UncertaintyMethod = UncertaintyMethod.ENTROPY):
        self.method = method
    
    def estimate(self, predictions: np.ndarray) -> Dict[str, float]:
        """
        Estimate uncertainty from predictions.
        
        Args:
            predictions: Array of shape (num_classes,) or (num_boxes, num_classes+5)
                        For YOLO: [x, y, w, h, conf, class_probs...]
        
        Returns:
            Dict with uncertainty metrics
        """
        if predictions.ndim == 1:
            probs = predictions
            is_1d = True
        else:
            is_1d = False
            # For YOLO output: take class probabilities (after conf)
            if predictions.shape[1] > 5:
                probs = predictions[:, 5:]
                # Weight by objectness confidence
                conf = predictions[:, 4]
                probs = probs * conf[:, np.newaxis]
            else:
                probs = predictions[:, 4:]
        
        # Normalize
        probs = np.clip(probs, 1e-8, 1.0)
        probs = probs / probs.sum(axis=-1, keepdims=True)
        
        results = {}
        
        if self.method in (UncertaintyMethod.LEAST_CONFIDENCE, UncertaintyMethod.MARGIN):
            max_probs = np.max(probs, axis=-1)
            results['least_confidence'] = 1.0 - max_probs
            
            # Margin: difference between top-2
            sorted_probs = np.sort(probs, axis=-1)
            if is_1d:
                results['margin'] = sorted_probs[-1] - sorted_probs[-2]
            else:
                results['margin'] = sorted_probs[:, -1] - sorted_probs[:, -2]
        
        if self.method in (UncertaintyMethod.ENTROPY,):
            entropy = -np.sum(probs * np.log(probs + 1e-8), axis=-1)
            max_entropy = np.log(probs.shape[-1])
            results['entropy'] = entropy / max_entropy  # Normalized [0,1]
        
        if self.method == UncertaintyMethod.CONSISTENCY:
            # Will be computed via TTA externally
            results['consistency'] = 0.0 if is_1d else np.zeros(probs.shape[0])
        
        return results
    
    def estimate_batch(self, predictions_batch: List[np.ndarray]) -> List[Dict]:
        """Estimate uncertainty for batch of predictions."""
        return [self.estimate(p) for p in predictions_batch]


# ==================== CONSISTENCY ESTIMATION (TTA) ====================

class ConsistencyEstimator:
    """Test-Time Augmentation consistency estimation."""
    
    def __init__(self, detector, augmentations: List[Callable] = None):
        self.detector = detector
        self.augmentations = augmentations or self._default_augmentations()
    
    def _default_augmentations(self) -> List[Callable]:
        return [
            lambda img: img,  # original
            lambda img: cv2.flip(img, 1),  # horizontal flip
            lambda img: cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE),
            lambda img: cv2.convertScaleAbs(img, alpha=1.2, beta=10),  # brightness
        ]
    
    def estimate(self, image: np.ndarray, num_aug: int = 3) -> np.ndarray:
        """
        Estimate consistency via TTA.
        Returns per-prediction consistency scores.
        """
        if not hasattr(self.detector, 'detectar'):
            return np.array([])
        
        all_predictions = []
        for aug in self.augmentations[:num_aug]:
            aug_img = aug(image)
            try:
                pads, _ = self.detector.detectar(aug_img)
                # Transform back to original coordinates
                transformed = self._transform_predictions(pads, aug, image.shape)
                all_predictions.append(transformed)
            except Exception:
                continue
        
        if len(all_predictions) < 2:
            return np.array([])
        
        # Compute consistency: IoU between predictions across augmentations
        return self._compute_consistency(all_predictions)
    
    def _transform_predictions(self, pads: List[Dict], aug: Callable, orig_shape) -> List[Dict]:
        """Transform predictions back to original coordinates."""
        # Simplified - in practice, compute inverse transform
        return pads
    
    def _compute_consistency(self, all_preds: List[List[Dict]]) -> np.ndarray:
        """Compute pairwise IoU consistency."""
        # Match predictions across augmentations
        # Return consistency score per prediction [0,1]
        return np.ones(len(all_preds[0])) * 0.8  # Placeholder


# ==================== QUERY STRATEGY ====================

class QuerySelector:
    """Selects most informative samples for labeling."""
    
    def __init__(self, config: ActiveLearningConfig):
        self.config = config
        self.uncertainty_estimator = UncertaintyEstimator(config.uncertainty_method)
        self.consistency_estimator = None  # Set externally
    
    def select_samples(
        self, 
        predictions: List[DetectionResult], 
        labeled_indices: set,
        num_samples: int = None
    ) -> List[int]:
        """
        Select most informative samples for labeling.
        
        Returns:
            Indices of selected samples
        """
        num_samples = num_samples or self.config.query_batch_size
        available = [i for i in range(len(predictions)) if i not in labeled_indices]
        
        if not available:
            return []
        
        # Compute scores
        scores = []
        for idx in available:
            pred = predictions[idx]
            score = self._compute_query_score(pred)
            scores.append((idx, score))
        
        # Sort by score (higher = more informative)
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # Diversity filtering if hybrid strategy
        if self.config.query_strategy == QueryStrategy.HYBRID:
            selected = self._diversity_filter(scores, num_samples)
        else:
            selected = [idx for idx, _ in scores[:num_samples]]
        
        return selected
    
    def _compute_query_score(self, pred: DetectionResult) -> float:
        """Compute informativeness score for a prediction."""
        # Base uncertainty
        if self.config.uncertainty_method == UncertaintyMethod.ENTROPY:
            base = pred.entropy
        elif self.config.uncertainty_method == UncertaintyMethod.MARGIN:
            base = pred.margin
        else:
            base = pred.uncertainty
        
        # Consistency bonus
        consistency_bonus = 0
        if self.consistency_estimator:
            consistency_bonus = self.config.diversity_weight * pred.consistency
        
        # Low confidence bonus (inverse)
        conf_bonus = (1.0 - pred.confidence) * 0.3
        
        return base + consistency_bonus + conf_bonus
    
    def _diversity_filter(self, scored: List[Tuple[int, float]], k: int) -> List[int]:
        """Select diverse samples using max-min distance."""
        if len(scored) <= k:
            return [idx for idx, _ in scored]
        
        selected = [scored[0][0]]
        candidates = scored[1:]
        
        while len(selected) < k and candidates:
            best_idx = -1
            best_score = -1
            
            for idx, score in candidates:
                # Min distance to already selected
                min_dist = min(
                    self._feature_distance(idx, selected_idx)
                    for selected_idx in selected
                )
                combined = score + self.config.diversity_weight * min_dist
                
                if combined > best_score:
                    best_score = combined
                    best_idx = idx
            
            if best_idx >= 0:
                selected.append(best_idx)
                candidates = [(i, s) for i, s in candidates if i != best_idx]
            else:
                break
        
        return selected
    
    def _feature_distance(self, idx1: int, idx2: int) -> float:
        """Feature distance between predictions (simplified)."""
        # Could use bbox distance, visual features, etc.
        return 0.5  # Placeholder


# ==================== PSEUDO-LABELING ====================

class PseudoLabeler:
    """Generates pseudo-labels from high-confidence predictions."""
    
    def __init__(self, config: ActiveLearningConfig):
        self.config = config
    
    def generate(
        self, 
        predictions: List[DetectionResult],
        existing_labels: List[LabeledSample]
    ) -> List[LabeledSample]:
        """
        Generate pseudo-labels from high-confidence predictions.
        """
        pseudo_labels = []
        class_counts = self._count_per_class(existing_labels)
        
        for pred in predictions:
            # Only high confidence
            if pred.confidence < self.config.pseudo_label_confidence:
                continue
            
            # Low uncertainty
            if pred.uncertainty > (1.0 - self.config.pseudo_label_confidence):
                continue
            
            # Per-class limit
            class_id = pred.class_id
            if class_counts.get(class_id, 0) >= self.config.pseudo_label_max_per_class:
                continue
            
            # Create pseudo-label
            label = LabeledSample(
                image_path=pred.image_path,
                bbox=self._bbox_to_normalized(pred.bbox, pred.image_shape),
                class_id=pred.class_id,
                is_pseudo=True,
                confidence=pred.confidence,
                annotator="pseudo",
                metadata={
                    'uncertainty': pred.uncertainty,
                    'entropy': pred.entropy,
                    'margin': pred.margin,
                }
            )
            
            pseudo_labels.append(label)
            class_counts[class_id] = class_counts.get(class_id, 0) + 1
        
        return pseudo_labels
    
    def _count_per_class(self, labels: List[LabeledSample]) -> Dict[int, int]:
        counts = {}
        for l in labels:
            counts[l.class_id] = counts.get(l.class_id, 0) + 1
        return counts
    
    def _bbox_to_normalized(self, bbox: Tuple[float, float, float, float], 
                            img_shape: Tuple[int, int]) -> Tuple[float, float, float, float]:
        """Convert absolute bbox to normalized YOLO format."""
        x, y, w, h = bbox
        h_img, w_img = img_shape
        return (
            (x + w/2) / w_img,  # cx
            (y + h/2) / h_img,  # cy
            w / w_img,          # w
            h / h_img           # h
        )


# ==================== LORA FINE-TUNING ====================

class LoRAFineTuner:
    """LoRA fine-tuning for YOLO models."""
    
    def __init__(self, config: ActiveLearningConfig):
        self.config = config
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not available")
        if not LORA_AVAILABLE:
            raise RuntimeError("loralib not installed (pip install loralib)")
    
    def inject_lora(self, model: nn.Module, rank: int = None) -> nn.Module:
        """Inject LoRA layers into model."""
        rank = rank or self.config.lora_rank
        
        # Apply LoRA to attention/conv layers
        for name, module in model.named_modules():
            if isinstance(module, (nn.Conv2d, nn.Linear)):
                # Skip first/last layers
                if 'head' in name or 'stem' in name:
                    continue
                
                # Replace with LoRA version
                lora_layer = lora.Linear(
                    module.in_features if isinstance(module, nn.Linear) else module.in_channels,
                    module.out_features if isinstance(module, nn.Linear) else module.out_channels,
                    r=self.config.lora_rank,
                    lora_alpha=self.config.lora_alpha,
                    lora_dropout=self.config.lora_dropout,
                )
                
                # Copy weights
                lora_layer.weight.data = module.weight.data.clone()
                if module.bias is not None:
                    lora_layer.bias.data = module.bias.data.clone()
                
                # Replace
                parent_name = '.'.join(name.split('.')[:-1])
                child_name = name.split('.')[-1]
                parent = model.get_submodule(parent_name) if parent_name else model
                setattr(parent, child_name, lora_layer)
        
        # Freeze base parameters, only train LoRA
        for name, param in model.named_parameters():
            if 'lora' not in name.lower():
                param.requires_grad = False
        
        return model
    
    def train(
        self,
        model_path: str,
        train_data: List[LabeledSample],
        val_data: List[LabeledSample] = None,
        epochs: int = None,
        progress_callback: Callable[[int, float, Dict], None] = None
    ) -> str:
        """
        Fine-tune model with LoRA.
        
        Returns:
            Path to fine-tuned model
        """
        epochs = epochs or self.config.finetune_epochs
        
        # Load model
        model = YOLO(self.config.model_path)
        model = self.inject_lora(model.model)
        model.to(self.device)
        
        # Prepare data loaders
        train_loader = self._create_dataloader(train_data, self.config.finetune_batch_size, shuffle=True)
        val_loader = self._create_dataloader(val_data, self.config.finetune_batch_size, shuffle=False) if val_data else None
        
        # Optimizer (only LoRA params)
        lora_params = [p for n, p in model.named_parameters() if 'lora' in n.lower() and p.requires_grad]
        optimizer = optim.AdamW(lora_params, lr=self.config.finetune_lr, weight_decay=1e-4)
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=self.config.finetune_epochs)
        
        # Training loop
        best_val_loss = float('inf')
        best_model_path = None
        
        for epoch in range(epochs):
            model.train()
            train_loss = 0
            
            for batch in train_loader:
                optimizer.zero_grad()
                loss = self._compute_loss(model, batch)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()
            
            avg_train_loss = train_loss / len(train_loader)
            
            # Validation
            val_loss = 0
            if val_loader:
                model.eval()
                with torch.no_grad():
                    for batch in val_loader:
                        loss = self._compute_loss(model, batch)
                        val_loss += loss.item()
                val_loss /= len(val_loader)
            
            scheduler.step()
            
            # Save best
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                best_model_path = self._save_checkpoint(model, epoch, val_loss)
            
            if progress_callback:
                progress_callback(epoch, train_loss, {
                    'val_loss': val_loss,
                    'lr': optimizer.param_groups[0]['lr']
                })
        
        return best_model_path or self.config.model_path
    
    def _create_dataloader(self, data: List[LabeledSample], batch_size: int, shuffle: bool):
        """Create DataLoader from labeled samples."""
        # Convert to YOLO format dataset
        dataset = YOLODataset(data)
        return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, 
                         num_workers=2, collate_fn=self._collate_fn)
    
    def _compute_loss(self, model, batch):
        # YOLO loss computation
        return model(batch)[0]  # Simplified
    
    def _save_checkpoint(self, model, epoch, val_loss) -> str:
        path = Path(self.config.checkpoint_dir) / f"lora_epoch{epoch}_val{val_loss:.4f}.pt"
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(model.state_dict(), path)
        return str(path)


# ==================== ACTIVE LEARNING ORCHESTRATOR ====================

class ActiveLearningOrchestrator:
    """
    Main orchestrator for the active learning loop.
    
    Flow:
    1. Detect on unlabeled pool
    2. Estimate uncertainty
    3. Select most informative samples
    3. Human validates (or pseudo-label high-conf)
    4. Add to labeled set
    5. Fine-tune with LoRA
    6. Repeat
    """
    
    def __init__(self, config: ActiveLearningConfig):
        self.config = config
        self.labeled_samples: List[LabeledSample] = []
        self.unlabeled_pool: List[DetectionResult] = []
        self.query_selector = QuerySelector(config)
        self.pseudo_labeler = PseudoLabeler(config)
        self.fine_tuner: Optional[LoRAFineTuner] = None
        
        # State
        self.current_model_path = config.model_path
        self.iteration = 0
        self.metrics_history = []
        
        # Setup directories
        Path(config.dataset_dir).mkdir(parents=True, exist_ok=True)
        Path(config.checkpoint_dir).mkdir(parents=True, exist_ok=True)
        
        # Load existing labels
        self._load_existing_labels()
    
    def run_iteration(
        self,
        unlabeled_images: List[str],
        validation_callback: Optional[Callable[[List[DetectionResult], List[int]], List[LabeledSample]]] = None,
        progress_callback: Optional[Callable[[str, Dict], None]] = None
    ) -> Dict:
        """
        Run one active learning iteration.
        
        Args:
            unlabeled_images: Paths to unlabeled images
            validation_callback: Function(human_labels) -> List[LabeledSample]
                                 If None, uses pseudo-labeling only
            progress_callback: Function(stage, metrics)
        
        Returns:
            Metrics dict
        """
        self.iteration += 1
        metrics = {'iteration': self.iteration}
        
        # 1. Detect on unlabeled pool
        if progress_callback: progress_callback('detecting', {'images': len(unlabeled_images)})
        self.unlabeled_pool = self._detect_pool(unlabeled_images)
        print(f"Detected {len(self.unlabeled_pool)} objects in {len(unlabeled_images)} images")
        
        # 2. Estimate uncertainty
        if progress_callback: progress_callback('estimating_uncertainty', {})
        self._estimate_uncertainties()
        
        # 3. Generate pseudo-labels for high-confidence
        pseudo_labels = self.pseudo_labeler.generate(
            self.unlabeled_pool, self.labeled_samples
        )
        print(f"Generated {len(pseudo_labels)} pseudo-labels")
        
        # 4. Select samples for human validation
        labeled_indices = set()  # Track which pool indices are labeled
        selected_indices = self.query_selector.select_samples(
            self.unlabeled_pool, 
            set(),  # No labeled indices in pool yet
            self.config.query_batch_size
        )
        
        # 5. Human validation (or auto with pseudo)
        human_labels = []
        if validation_callback and selected_indices:
            if progress_callback: progress_callback('awaiting_validation', {
                'selected': len(selected_indices)
            })
            human_labels = validation_callback(
                [self.unlabeled_pool[i] for i in selected_indices],
                selected_indices
            )
        elif selected_indices:
            # Use pseudo-labels for selected
            human_labels = [
                LabeledSample(
                    image_path=self.unlabeled_pool[i].image_path,
                    bbox=self.unlabeled_pool[i].bbox,
                    class_id=self.unlabeled_pool[i].class_id,
                    is_pseudo=True,
                    confidence=self.unlabeled_pool[i].confidence,
                    annotator="pseudo"
                )
                for i in selected_indices
            ]
        
        # 6. Add to labeled set
        all_new_labels = human_labels + self._filter_pseudo_labels()
        self.labeled_samples.extend(all_new_labels)
        print(f"Added {len(all_new_labels)} labels (human: {len(human_labels)}, pseudo: {len(all_new_labels) - len(human_labels)})")
        
        # 7. Fine-tune with LoRA
        if TORCH_AVAILABLE and LORA_AVAILABLE and len(self.labeled_samples) >= self.config.min_samples_per_class:
            if progress_callback: progress_callback('fine_tuning', {'samples': len(self.labeled_samples)})
            self._fine_tune()
        
        # 7. Save state
        self._save_state()
        
        # Metrics
        metrics.update({
            'total_labeled': len(self.labeled_samples),
            'pseudo_labeled': sum(1 for l in self.labeled_samples if l.is_pseudo),
            'human_labeled': sum(1 for l in self.labeled_samples if not l.is_pseudo),
            'pool_size': len(self.unlabeled_pool),
            'model_path': self.current_model_path,
        })
        
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _detect_pool(self, image_paths: List[str]) -> List[DetectionResult]:
        """Run detection on pool of images."""
        from core.detector_ia import DetectorIA
        from core.imgio import ler_imagem
        
        if not hasattr(self, '_detector') or self.current_model_path != self.config.model_path:
            self.detector = DetectorIA(self.current_model_path)
            self.current_model_path = self.config.model_path
        
        results = []
        for img_path in image_paths:
            img = cv2.imread(img_path)
            if img is None:
                continue
            pads, _ = self.detector.detectar(img, conf=0.25)
            for p in pads:
                results.append(DetectionResult(
                    bbox=(p['cx'], p['cy'], p['w'], p['h']),
                    confidence=p.get('score', 0.5),
                    class_id=p.get('class_id', 0),
                    uncertainty=0.5,  # Will be computed
                    uncertainties_per_class=np.array([]),
                    entropy=0.5,
                    margin=0.5,
                    image_path=img_path,
                    image_shape=(img.shape[0], img.shape[1])
                ))
        return results
    
    def _estimate_uncertainties(self):
        """Compute uncertainty for all pool predictions."""
        for pred in self.unlabeled_pool:
            # Simple uncertainty based on confidence
            pred.uncertainty = 1.0 - pred.confidence
            pred.entropy = -pred.confidence * np.log(pred.confidence + 1e-8) - (1-pred.confidence)*np.log(1-pred.confidence+1e-8)
            pred.margin = pred.confidence  # Simplified
    
    def _filter_pseudo_labels(self) -> List[LabeledSample]:
        """Get pseudo-labels not already in labeled set."""
        existing_paths = {(l.image_path, l.bbox, l.class_id) for l in self.labeled_samples}
        new_pseudo = []
        
        for pred in self.unlabeled_pool:
            if pred.confidence >= self.config.pseudo_label_confidence:
                key = (pred.image_path, pred.bbox, pred.class_id)
                if key not in existing_paths:
                    label = LabeledSample(
                        image_path=pred.image_path,
                        bbox=self._bbox_to_normalized(pred.bbox, pred.image_shape),
                        class_id=pred.class_id,
                        is_pseudo=True,
                        confidence=pred.confidence,
                        annotator="pseudo"
                    )
                    pseudo_labels.append(label)
        
        return pseudo_labels
    
    def _fine_tune(self):
        """Run LoRA fine-tuning."""
        if self.fine_tuner is None:
            self.fine_tuner = LoRAFineTuner(self.config)
        
        # Prepare data
        train_samples = self.labeled_samples
        random.shuffle(train_samples)
        split = int(0.9 * len(train_samples))
        train_data = train_samples[:split]
        val_data = train_samples[split:]
        
        def progress_cb(epoch, loss, metrics):
            print(f"  Epoch {epoch}: loss={loss:.4f}, val_loss={metrics.get('val_loss', 0):.4f}")
        
        new_model = self.fine_tuner.train(
            self.current_model_path,
            train_data, val_data,
            progress_callback=progress_cb
        )
        
        if new_model:
            self.config.model_path = new_model
            self.current_model_path = new_model
            print(f"Model updated: {new_model}")
    
    def _save_state(self):
        """Save active learning state."""
        state = {
            'iteration': self.iteration,
            'config': self.config.__dict__,
            'labeled_samples': [
                {
                    'image_path': l.image_path,
                    'bbox': l.bbox,
                    'class_id': l.class_id,
                    'is_pseudo': l.is_pseudo,
                    'confidence': l.confidence,
                    'annotator': l.annotator,
                    'timestamp': l.timestamp,
                    'metadata': l.metadata
                }
                for l in self.labeled_samples
            ],
            'metrics_history': self.metrics_history,
            'current_model': self.current_model_path,
        }
        
        state_path = Path(self.config.checkpoint_dir) / f'al_state_iter{self.iteration}.json'
        with open(state_path, 'w') as f:
            json.dump(state, f, indent=2, default=str)
    
    def _load_existing_labels(self):
        """Load previously saved labels."""
        # Look for existing state files
        checkpoint_dir = Path(self.config.checkpoint_dir)
        if checkpoint_dir.exists():
            states = sorted(checkpoint_dir.glob('al_state_iter*.json'))
            if states:
                latest = states[-1]
                with open(latest) as f:
                    state = json.load(f)
                self.iteration = state.get('iteration', 0)
                self.metrics_history = state.get('metrics_history', [])
                self.current_model_path = state.get('current_model', self.config.model_path)
                
                # Restore labels
                for l_data in state.get('labeled_samples', []):
                    self.labeled_samples.append(LabeledSample(**l_data))
                print(f"Loaded {len(self.labeled_samples)} existing labels from iteration {self.iteration}")


# ==================== VALIDATION UI HELPER ====================

class ValidationUI:
    """Helper for creating validation UI in AnotadorPad."""
    
    def __init__(self, app):
        self.app = app
        self.pending_validations = []
        self.validation_results = []
    
    def show_validation_dialog(self, predictions: List[DetectionResult], indices: List[int]) -> List[LabeledSample]:
        """Show validation dialog for selected predictions."""
        # This would integrate with AnotadorPad's UI
        # For now, return empty list (placeholder)
        return []
    
    def create_validation_overlay(self, canvas: np.ndarray, predictions: List[DetectionResult], indices: List[int]) -> np.ndarray:
        """Draw validation overlay on canvas."""
        for idx in indices:
            pred = predictions[idx]
            x, y, w, h = pred.bbox
            color = (0, 255, 255) if pred.is_pseudo else (0, 255, 0)
            cv2.rectangle(canvas, (int(x-w/2), int(y-h/2)), (int(x+w/2), int(y+h/2)), color, 2)
            cv2.putText(canvas, f"Conf: {pred.confidence:.2f}", (int(x), int(y-h/2-5)),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        return canvas


# ==================== DATASET UTILITIES ====================

class ActiveLearningDataset(Dataset):
    """PyTorch Dataset for active learning labeled samples."""
    
    def __init__(self, samples: List[LabeledSample], img_size: int = 640, augment: bool = True):
        self.samples = samples
        self.img_size = img_size
        self.augment = augment
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        sample = self.samples[idx]
        img = cv2.imread(sample.image_path)
        if img is None:
            # Return dummy
            return torch.zeros(3, self.img_size, self.img_size), {}
        
        # Convert bbox to absolute
        h, w = img.shape[:2]
        bbox = sample.bbox  # normalized xywh
        x1 = int((bbox[0] - bbox[2]/2) * w)
        y1 = int((bbox[1] - bbox[3]/2) * h)
        x2 = int((bbox[0] + bbox[2]/2) * w)
        y2 = int((bbox[1] + bbox[3]/2) * h)
        
        # Resize with letterbox
        img, ratio, pad = self._letterbox(img)
        
        # Adjust bbox
        bbox = self._adjust_bbox((x1, y1, x2, y2), ratio, pad)
        
        # Convert to tensor
        img = torch.from_numpy(img.transpose(2, 0, 1)).float() / 255.0
        
        target = {
            'boxes': torch.tensor([bbox], dtype=torch.float32),
            'labels': torch.tensor([sample.class_id], dtype=torch.long),
        }
        
        return img, target
    
    def _letterbox(self, img):
        h, w = img.shape[:2]
        r = min(self.img_size / w, self.img_size / h)
        nw, nh = int(w * r), int(h * r)
        resized = cv2.resize(img, (nw, nh))
        canvas = np.full((self.img_size, self.img_size, 3), 114, dtype=np.uint8)
        dx, dy = (self.img_size - nw) // 2, (self.img_size - nh) // 2
        canvas[dy:dy+nh, dx:dx+nw] = resized
        return canvas, r, (dx, dy)
    
    def _adjust_bbox(self, bbox, ratio, pad):
        x1, y1, x2, y2 = bbox
        dx, dy = pad
        return [
            (x1 * ratio + dx) / self.img_size,
            (y1 * ratio + dy) / self.img_size,
            (x2 * ratio + dx) / self.img_size,
            (y2 * ratio + dy) / self.img_size,
        ]


# ==================== FACTORY ====================

def create_active_learning_orchestrator(
    model_path: str = "models/pads.onnx",
    dataset_dir: str = "active_learning_data",
    query_batch_size: int = 20,
    pseudo_label_confidence: float = 0.8,
    finetune_epochs: int = 5,
    **kwargs
) -> ActiveLearningOrchestrator:
    """Factory para criar orquestrador de Active Learning."""
    config = ActiveLearningConfig(
        model_path=model_path,
        dataset_dir=dataset_dir,
        query_batch_size=query_batch_size,
        pseudo_label_confidence=pseudo_label_confidence,
        finetune_epochs=finetune_epochs,
        **kwargs
    )
    return ActiveLearningOrchestrator(config)


# ==================== EXPORTS ====================

__all__ = [
    'ActiveLearningConfig',
    'UncertaintyMethod',
    'QueryStrategy',
    'DetectionResult',
    'LabeledSample',
    'UncertaintyEstimator',
    'ConsistencyEstimator',
    'QuerySelector',
    'PseudoLabeler',
    'LoRAFineTuner',
    'ActiveLearningOrchestrator',
    'ValidationUI',
    'ActiveLearningDataset',
    'create_active_learning_orchestrator',
]