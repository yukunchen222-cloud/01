"""
数据校验节点
验证提取的账目数据是否完整和正确
"""
from typing import List, Dict, Any
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from coze_coding_utils.runtime_ctx.context import Context
from graphs.state import ValidationInput, ValidationOutput


def data_validation_node(
    state: ValidationInput,
    config: RunnableConfig,
    runtime: Runtime[Context]
) -> ValidationOutput:
    """
    title: 数据校验
    desc: 验证提取的账目数据是否完整和正确
    
    integrations:
    """
    ctx = runtime.context
    
    extracted_data = state.extracted_data
    data_type = state.data_type
    
    errors: List[str] = []
    validated_data: Dict[str, Any] = {}
    
    # 基本校验规则
    if not extracted_data:
        errors.append("提取的数据为空")
        return ValidationOutput(
            validation_passed=False,
            validated_data={},
            errors=errors
        )
    
    # 根据数据类型进行校验
    if data_type == "sale":
        # 销售数据校验
        if "amount" not in extracted_data and "total_price" not in extracted_data:
            errors.append("缺少销售金额")
        if "items" not in extracted_data and "product_name" not in extracted_data:
            errors.append("缺少商品信息")
            
    elif data_type == "purchase":
        # 进货数据校验
        if "supplier" not in extracted_data:
            errors.append("缺少供应商信息")
        if "total_amount" not in extracted_data:
            errors.append("缺少进货金额")
            
    elif data_type == "expense":
        # 支出数据校验
        if "amount" not in extracted_data:
            errors.append("缺少支出金额")
        if "category" not in extracted_data:
            errors.append("缺少支出类别")
    
    # 添加时间戳
    from datetime import datetime
    validated_data = {
        **extracted_data,
        "data_type": data_type,
        "validated_at": datetime.now().isoformat()
    }
    
    validation_passed = len(errors) == 0
    
    return ValidationOutput(
        validation_passed=validation_passed,
        validated_data=validated_data if validation_passed else {},
        errors=errors
    )
