"""Walk-forward analýza.

Spec: Blok 3 ÚKOL 12.
- Train: 2019–2023 (5 let)
- Test: 2024–Q1 2026 (2,25 let)
- Rolling window: 6m train → 1m test, min 12 iterací
- Práh: všechny OOS měsíce profitabilní (max 2 ztrátové)
"""
