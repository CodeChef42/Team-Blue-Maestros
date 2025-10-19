import React from "react";

export default function MetricBar({
  label,
  value,
  suffix = "%",
  color = "bg-blue-500",
}) {
  const width = Math.min(value, 100);
  return (
    <div className="mb-3">
      <div className="flex justify-between text-xs text-gray-700">
        <span>{label}</span>
        <span>
          {value.toFixed(1)}
          {suffix}
        </span>
      </div>
      <div className="w-full h-2 bg-gray-200 rounded">
        <div
          className={`${color} h-2 rounded transition-all duration-300`}
          style={{ width: `${width}%` }}
        ></div>
      </div>
    </div>
  );
}
