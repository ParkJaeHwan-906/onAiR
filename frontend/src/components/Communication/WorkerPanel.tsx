import React from "react";
import DrawingPreview from "./DrawingPreview"
import WorkerHeader from "./WorkerHeader";
import "../../styles/Communication/WorkerPanel.css"

const WorkerPanel = () => {
    return (
        <div className="work-panel">
            <WorkerHeader />
            <DrawingPreview />
        </div>
    )
}

export default WorkerPanel