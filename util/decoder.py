def json_safe_encoder(obj):
    # 处理 TextContent
    if obj.__class__.__name__ == "TextContent":
        return {
            "type": obj.type,
            "text": obj.text,
            "annotations": obj.annotations,
            "meta": obj.meta,
        }

    # 兜底：不认识的类型直接报错（安全）
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")