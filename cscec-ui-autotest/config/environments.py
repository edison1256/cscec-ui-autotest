"""
多环境 URL 映射

环境说明：
- UAT（irp-uat.cscec.com / cloud-uat.cscec.com）：测试环境，日常测试用
- PRE（irp-pre.cscec.com / cloud-pre.cscec.com）：预发环境，上线生产前验收测试用
- PROD（irp.cscec.com / cloud.cscec.com）：生产环境
"""

# 控制台后门直登路由（账号密码直登，绕过 4A/SSO）。
# 仅用于环境装配类运维操作，不得用于业务用例断言。
ADMIN_LOGIN_ROUTE = "/udpweb/portal/index.html#/login"

# 计量订阅套件使用的租户映射（按环境）。
#
# 背景：`ensure_tenant(page, shape)` 靠工作台菜单形态判定当前租户是否就绪——
# "zjy" 需要出现「我的订阅」，"sz" 需要出现「订阅中心」。实测发现**同一个租户名
# 在不同环境给出不同形态**，因此不能写死成全局常量。
#
# 实测来源（2026-11-11，账号 20431644 / 陈方达）：
#   PRE：技术与大数据平台项目组=我的订阅；中建数字科技有限公司=订阅中心；
#        测试专用租户=订阅中心；域名拆分测试=我的订阅
#   UAT：技术与大数据平台项目组=我的订阅；中建数字科技有限公司=我的订阅；
#        测试租户1234=订阅中心；0417测试租户=订阅中心
#   证据：reports/identity-matrix/_pre_tenant_shapes.json / _uat_app_subscription.json
#
# 注意：判断形态必须走「工作台 ?suitKey=portal -> 点『应用订阅』」这条路径，
# 只看营销门户或工作台首页文本会误判为 none。
#
# prod 保持改动前的原值（未经实测，不擅自改生产行为）。
METERING_TENANTS = {
    "prod": {
        "zjy": "中建云",
        "sz": "中建数字科技有限公司",
    },
    "pre": {
        "zjy": "技术与大数据平台项目组",
        "sz": "中建数字科技有限公司",
    },
    "uat": {
        "zjy": "技术与大数据平台项目组",
        "sz": "测试租户1234",
    },
}

# 计量订阅套件用于触发账号 hover 面板的显示名（工作台右上角）。
# 实测该面板由显示名文本触发，用 avatar/user class 匹配不稳定。
METERING_DISPLAY_NAME = {
    "prod": "陈方达",
    "pre": "陈方达",
    "uat": "陈方达",
}

# 工作台 / 控制台 SPA 的 suitKey（按环境实测，不能跨环境复用）。
#   pre.console = 1899427585366003726（登录落地 URL 实测）
#   uat.console = 1895404747812683790（登录落地 URL 实测）
#   prod.console = 1899427585366003724（沿用 environments 内既有常量）
# workbench 统一用 "portal"（PRE 与 UAT 均实测可用）。
METERING_SUIT_KEYS = {
    "prod": {"workbench": "portal", "console": "1899427585366003724"},
    "pre": {"workbench": "portal", "console": "1899427585366003726"},
    "uat": {"workbench": "portal", "console": "1895404747812683790"},
}

# 控制台域名下的工作台套件 key（与门户域的 "portal" 不是同一个值）。
# 2026-11-12 实测 PRE：portal 域工作台用 suitKey=portal；
# 而 irp 域点「应用订阅」后的真实路由是 suitKey=1899427585366003727。
# 两者不可互换 —— 用 portal 去打开 irp 域工作台只会停在磁贴首页。
METERING_SUIT_KEYS_ON_CONSOLE_DOMAIN = {
    "prod": "1899427585366003725",
    "pre": "1899427585366003727",
    "uat": "",
}



# 直链兜底路由：当菜单入口在某环境未暴露时，可在此填入真实 SPA 路由作为
# 导航兜底。键名约定：service_supply / my_documents / manual_inspection。
# 未填写（空字典）时，弹性导航将直接降级为安全跳过，避免假失败。
DEEP_LINKS = {
    "prod": {},
    "pre": {},
    "uat": {},
}

DATA_RESOURCE_ROUTE = (
    "/udpweb/portal/index.html?loginType=1&"
    "#/sub/resource/resource/dataResources"
    "?suitKey=1895404747812683790"
    "&routeName=resource"
    "&appTitle=%E6%95%B0%E6%8D%AE%E8%B5%84%E6%BA%90%E7%AE%A1%E7%90%86"
    "&mc=1895404747812683790"
    "&mn=%E6%8E%A7%E5%88%B6%E5%8F%B0"
    "&mt=module"
    "&menuCode=1930918519330086914"
)

LAYER_SETTINGS_ROUTE_BY_ENV = {
    "prod": (
        "/udpweb/portal/index.html?#/sub/resource/systemManage/layerSet"
        "?suitKey=1899427585366003724"
        "&routeName=resource"
        "&appTitle=%E6%95%B0%E6%8D%AE%E5%88%86%E5%B1%82%E8%AE%BE%E7%BD%AE"
    ),
    "pre": (
        "/udpweb/portal/index.html?#/sub/resource/systemManage/layerSet"
        "?suitKey=1899427585366003726"
        "&routeName=resource"
        "&appTitle=%E6%95%B0%E6%8D%AE%E5%88%86%E5%B1%82%E8%AE%BE%E7%BD%AE"
    ),
    "uat": (
        "/udpweb/portal/index.html?#/sub/resource/systemManage/layerSet"
        "?suitKey=1899427585366003724"
        "&routeName=resource"
        "&appTitle=%E6%95%B0%E6%8D%AE%E5%88%86%E5%B1%82%E8%AE%BE%E7%BD%AE"
    ),
}

DOC_CENTER_WORKBENCH_ROUTE = (
    "/udpweb/portal/index.html#/portal/home/workbench"
    "?suitKey=1899427585366003724"
    "&mc=1899427585366003724"
    "&mn=%E6%96%87%E6%A1%A3%E4%B8%AD%E5%BF%83"
    "&mt=module"
    "&appTitle=%E5%B7%A5%E4%BD%9C%E5%8F%B0"
)

ENVIRONMENTS = {
    "prod": {
        "BASE_URL": "https://irp.cscec.com/",
        "CONSOLE_BASE_URL": "https://irp.cscec.com/",
        "PORTAL_BASE_URL": "https://cloud.cscec.com/",
        "WORKBENCH_BASE_URL": "https://cloud.cscec.com/",
        "MOBILE_BASE_URL": "https://cloud.cscec.com/",
        "DOC_CENTER_URL": "https://cloud.cscec.com" + DOC_CENTER_WORKBENCH_ROUTE,
        "DOC_CENTER_FALLBACK_URL": "https://irp.cscec.com" + DOC_CENTER_WORKBENCH_ROUTE,
        "DATA_RESOURCE_ROUTE": DATA_RESOURCE_ROUTE,
        "LAYER_SETTINGS_ROUTE": LAYER_SETTINGS_ROUTE_BY_ENV["prod"],
        "ADMIN_LOGIN_URL": "https://irp.cscec.com" + ADMIN_LOGIN_ROUTE,
        "DEEP_LINKS": DEEP_LINKS["prod"],
    },
    "pre": {
        "BASE_URL": "https://irp-pre.cscec.com/",
        "CONSOLE_BASE_URL": "https://irp-pre.cscec.com/",
        "PORTAL_BASE_URL": "https://cloud-pre.cscec.com/",
        "WORKBENCH_BASE_URL": "https://cloud-pre.cscec.com/",
        "MOBILE_BASE_URL": "https://cloud-pre.cscec.com/",
        "DOC_CENTER_URL": "https://irp-pre.cscec.com" + DOC_CENTER_WORKBENCH_ROUTE,
        "DOC_CENTER_FALLBACK_URL": "https://cloud-pre.cscec.com" + DOC_CENTER_WORKBENCH_ROUTE,
        "DATA_RESOURCE_ROUTE": DATA_RESOURCE_ROUTE,
        "LAYER_SETTINGS_ROUTE": LAYER_SETTINGS_ROUTE_BY_ENV["pre"],
        "ADMIN_LOGIN_URL": "https://irp-pre.cscec.com" + ADMIN_LOGIN_ROUTE,
        "DEEP_LINKS": DEEP_LINKS["pre"],
    },
    "uat": {
        "BASE_URL": "https://irp-uat.cscec.com/",
        "CONSOLE_BASE_URL": "https://irp-uat.cscec.com/",
        "PORTAL_BASE_URL": "https://cloud-uat.cscec.com/",
        "WORKBENCH_BASE_URL": "https://cloud-uat.cscec.com/",
        "MOBILE_BASE_URL": "https://cloud-uat.cscec.com/",
        "DOC_CENTER_URL": "https://irp-uat.cscec.com" + DOC_CENTER_WORKBENCH_ROUTE,
        "DOC_CENTER_FALLBACK_URL": "https://cloud-uat.cscec.com" + DOC_CENTER_WORKBENCH_ROUTE,
        "DATA_RESOURCE_ROUTE": DATA_RESOURCE_ROUTE,
        "LAYER_SETTINGS_ROUTE": LAYER_SETTINGS_ROUTE_BY_ENV["uat"],
        "ADMIN_LOGIN_URL": "https://irp-uat.cscec.com" + ADMIN_LOGIN_ROUTE,
        "DEEP_LINKS": DEEP_LINKS["uat"],
    },
}
