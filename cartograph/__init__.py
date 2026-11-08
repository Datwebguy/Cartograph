"""Cartograph: verified executable world models for a Duck-style harness.

Harness-independent pieces (importable without the Duck harness installed):
  - cartograph.verifier   exact-replay verifier
  - cartograph.workspace  persistent world_model.py + verification log

Harness-dependent piece (needs the Duck harness on sys.path):
  - cartograph.agent      CartographToolAgent, a subclass of Duck's ToolAgent
"""
