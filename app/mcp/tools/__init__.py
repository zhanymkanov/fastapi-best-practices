"""
MCP 工具包 — 所有业务工具集中在此目录

工具分类：
  device_tools  — IoT 设备查询、状态监控
  health_tools  — 宠物健康分析、症状诊断
  ticket_tools  — 客服工单创建、状态查询
  member_tools  — 会员权益查询、资格核查
  ota_tools     — 设备 OTA 固件升级管理

每个工具继承 BaseMCPTool，通过 MCPRegistry 自动发现并注册。
"""
