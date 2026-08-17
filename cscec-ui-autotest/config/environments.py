"""
多环境 URL 映射

环境说明：
- UAT（irp-uat.cscec.com）：测试环境，日常测试用
- PRE（irp-pre.cscec.com）：预发环境，上线生产前验收测试用
- PROD（irp.cscec.com）：生产环境
"""

# 直链兜底路由：当菜单入口在某环境未暴露时，可在此填入真实 SPA 路由作为
# 导航兜底。键名约定：service_supply / my_documents / manual_inspection。
# 未填写（空字典）时，弹性导航将直接降级为安全跳过，避免假失败。
DEEP_LINKS = {
    "prod": {},
    "pre": {},
    "uat": {},
}

ENVIRONMENTS = {
    "prod": {
        "BASE_URL": "https://irp.cscec.com/",
        "DOC_CENTER_URL": (
            "https://irp.cscec.com/udpweb/portal/index.html#/portal/home/workbench"
            "?suitKey=1899427585366003724"
            "&mc=1899427585366003724"
            "&mn=%E6%96%87%E6%A1%A3%E4%B8%AD%E5%BF%83"
            "&mt=module"
            "&appTitle=%E5%B7%A5%E4%BD%9C%E5%8F%B0"
        ),
        "DEEP_LINKS": DEEP_LINKS["prod"],
    },
    "pre": {
        "BASE_URL": "https://irp-pre.cscec.com/",
        "DOC_CENTER_URL": (
            "https://irp-pre.cscec.com/udpweb/portal/index.html#/portal/home/workbench"
            "?suitKey=1899427585366003724"
            "&mc=1899427585366003724"
            "&mn=%E6%96%87%E6%A1%A3%E4%B8%AD%E5%BF%83"
            "&mt=module"
            "&appTitle=%E5%B7%A5%E4%BD%9C%E5%8F%B0"
        ),
        "DEEP_LINKS": DEEP_LINKS["pre"],
    },
    "uat": {
        "BASE_URL": "https://irp-uat.cscec.com/",
        "DOC_CENTER_URL": (
            "https://irp-uat.cscec.com/udpweb/portal/index.html#/portal/home/workbench"
            "?suitKey=1899427585366003724"
            "&mc=1899427585366003724"
            "&mn=%E6%96%87%E6%A1%A3%E4%B8%AD%E5%BF%83"
            "&mt=module"
            "&appTitle=%E5%B7%A5%E4%BD%9C%E5%8F%B0"
        ),
        "DEEP_LINKS": DEEP_LINKS["uat"],
    },
}
