"""
Lipinski五规则过滤模块

基于PubChem返回的物化性质进行类药性判断，无需rdkit。
Lipinski规则：
- 分子量 MW ≤ 500
- 脂水分配系数 XLogP ≤ 5
- 氢键供体 HBD ≤ 5
- 氢键受体 HBA ≤ 10
违反 ≤ 1 条 → 通过（类药性好）
"""

from typing import Optional


# Lipinski五规则阈值
LIPINSKI_RULES = {
    "MW": {"max": 500, "label": "分子量"},
    "XLogP": {"max": 5, "label": "脂水分配系数"},
    "HBD": {"max": 5, "label": "氢键供体"},
    "HBA": {"max": 10, "label": "氢键受体"},
}


def check_lipinski(properties: dict) -> dict:
    """
    对分子的物化性质进行Lipinski五规则检查

    Args:
        properties: get_molecule_properties返回的字典，需包含：
            molecular_weight, xlogp, hbd, hba
    Returns:
        {
            "passes": bool,           # 是否通过（违反≤1条）
            "violation_count": int,   # 违反条数
            "violations": list,       # 具体违反项
            "details": list           # 每条规则的详细检查结果
        }
    """
    # 从properties提取数值，兼容字符串类型
    values = {
        "MW": _safe_float(properties.get("molecular_weight")),
        "XLogP": _safe_float(properties.get("xlogp")),
        "HBD": _safe_int(properties.get("hbd")),
        "HBA": _safe_int(properties.get("hba")),
    }

    details = []
    violations = []

    for rule_key, rule in LIPINSKI_RULES.items():
        val = values[rule_key]
        threshold = rule["max"]
        label = rule["label"]

        if val is None:
            details.append({
                "rule": rule_key,
                "label": label,
                "value": None,
                "threshold": threshold,
                "status": "缺失",
            })
            continue

        passed = val <= threshold
        detail = {
            "rule": rule_key,
            "label": label,
            "value": val,
            "threshold": threshold,
            "status": "通过" if passed else "违反",
        }
        details.append(detail)

        if not passed:
            violations.append(f"{label}({rule_key}={val} > {threshold})")

    violation_count = len(violations)
    # Lipinski规则：违反≤1条视为通过
    passes = violation_count <= 1

    return {
        "passes": passes,
        "violation_count": violation_count,
        "violations": violations,
        "details": details,
    }


def _safe_float(val) -> Optional[float]:
    """安全转换为float"""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> Optional[int]:
    """安全转换为int"""
    if val is None:
        return None
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None