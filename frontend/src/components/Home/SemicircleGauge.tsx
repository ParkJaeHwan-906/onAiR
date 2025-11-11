import { ResponsivePie } from "@nivo/pie";
import "../../styles/SemicircleGauge.css";

type SemicircleGaugeProps = {
  value?: number;
  max?: number;
};

function SemicircleGauge({ value = 0, max = 100 }: SemicircleGaugeProps) {
  const safeMax = max > 0 ? max : 1;
  const clampedValue = Math.min(Math.max(value, 0), safeMax);
  const remainder = safeMax - clampedValue;

  const data = [
    { id: "filled", value: clampedValue, color: "#3B4A6B" },
    { id: "empty", value: remainder, color: "#ECEDF1" },
  ];

  return (
    <div className="semicircle-gauge-container">
      <ResponsivePie
        data={data}
        startAngle={-135}
        endAngle={135}
        sortByValue={false}
        colors={(datum) => datum.data.color as string}
        innerRadius={0.8}
        cornerRadius={45}
        activeOuterRadiusOffset={0}
        enableArcLinkLabels={false}
        enableArcLabels={false}
        padAngle={0}
      />
      <span className="semicircle-gauge-value">{value}%</span>
    </div>
  );
}

export default SemicircleGauge;
