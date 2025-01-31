# !/usr/bin/env python
# -- coding: utf-8 --
# @Time : 2021/6/18 14:05
# @Author : liumin
# @File : deeplabv3.py

"""
    Rethinking Atrous Convolution for Semantic Image Segmentation
    https://arxiv.org/pdf/1706.05587.pdf
"""

from itertools import chain
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

from src.models.backbones import build_backbone
from src.models.heads import build_head
from src.losses.seg_loss import CrossEntropyLoss2d
from src.utils.torch_utils import set_bn_momentum


class Deeplabv3(nn.Module):
    def __init__(self, dictionary=None, model_cfg=None):
        super().__init__()
        self.dictionary = dictionary
        self.model_cfg = model_cfg
        self.input_size = [1024, 2048]
        self.dummy_input = torch.zeros(1, 3, self.input_size[0], self.input_size[1])

        self.num_classes = len(self.dictionary)
        self.category = [v for d in self.dictionary for v in d.keys()]
        self.weight = [d[v] for d in self.dictionary for v in d.keys() if v in self.category]

        '''
        # backbone_cfg = {'name': 'MobileNetV2', 'subtype': 'mobilenet_v2', 'out_stages': [7], 'output_stride': 16, 'pretrained': True}
        backbone_cfg = {'name': 'ResNet', 'subtype': 'resnet50', 'out_stages': [4], 'output_stride': 16, 'pretrained': True}
        self.backbone = build_backbone(backbone_cfg)
        if backbone_cfg['output_stride'] == 8:
            dilations = [12, 24, 36]
        else:
            dilations = [6, 12, 18]
        head_cfg = {'name': 'Deeplabv3Head',  'in_channels': self.backbone.out_channels[0], 'dilations': dilations, 'num_classes': self.num_classes }
        self.head = build_head(head_cfg)
        '''
        self.model_cfg.HEAD.__setitem__('num_classes', self.num_classes)

        self.backbone = build_backbone(self.model_cfg.BACKBONE)
        self.head = build_head(self.model_cfg.HEAD)

        self.criterion = CrossEntropyLoss2d(weight=torch.from_numpy(np.array(self.weight)).float()).cuda()
        set_bn_momentum(self.backbone, momentum=0.01)


    def _init_weight(self, *stages):
        for m in chain(*stages):
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_uniform_(m.weight)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.BatchNorm2d) or isinstance(m, nn.Linear):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)


    def forward(self, imgs, targets=None, mode='infer', **kwargs):
        batch_size, ch, _, _ = imgs.shape
        x = self.backbone(imgs)
        x = self.head(x)
        outputs = F.interpolate(x, size=imgs.size()[2:], mode='bilinear', align_corners=False)

        if mode == 'infer':

            return torch.argmax(outputs, dim=1)
        else:
            losses = {}
            losses['ce_loss'] = self.criterion(outputs, targets)
            losses['loss'] = losses['ce_loss']

            if mode == 'val':
                return losses, torch.argmax(outputs, dim=1)
            else:
                return losses
