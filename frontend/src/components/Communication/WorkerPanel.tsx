// import React from "react";
import DrawingPreview from "./DrawingPreview";
import WorkerHeader from "./WorkerHeader";
import "../../styles/Communication/WorkerPanel.css";

interface PartnerInfo {
  senderAccountId: number;
  name: string;
  phone: string;
  equipmentName: string | null;
}

interface WorkerPanelProps {
  partnerInfo?: PartnerInfo | null;
}

const WorkerPanel = ({ partnerInfo }: WorkerPanelProps) => {
  return (
    <div className="work-panel">
      <WorkerHeader partnerInfo={partnerInfo} />
      <DrawingPreview />
    </div>
  );
};

export default WorkerPanel;
