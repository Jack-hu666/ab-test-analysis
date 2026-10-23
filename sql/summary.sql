-- 基础汇总（用 SQL 算，与 pandas 结果交叉验证）

-- @name: conversion_by_group
-- 每组人数与转化率（group 是 SQL 保留字，需用双引号引用）
SELECT
  "group",
  COUNT(*)                         AS n,
  SUM(converted)                   AS converted,
  ROUND(AVG(converted), 6)         AS cvr
FROM experiment
GROUP BY "group";

-- @name: amount_by_group
-- 每组总金额与人均金额（含未支付，金额为 0）
SELECT
  "group",
  COUNT(*)                         AS n,
  ROUND(SUM(amount), 2)            AS total_amount,
  ROUND(AVG(amount), 4)            AS avg_amount
FROM experiment
GROUP BY "group";

-- @name: amount_converted_by_group
-- 转化用户的人均支付金额（客单价）
SELECT
  "group",
  COUNT(*)                         AS n_converted,
  ROUND(AVG(amount), 4)            AS avg_aov
FROM experiment
WHERE converted = 1
GROUP BY "group";
