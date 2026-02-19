import React, { useState } from "react";
import type { Session } from "../../types";
import AlertsSection from "./AlertsSection";
import MedicationSection from "./MedicationSection";
import DifferentialSection from "./DifferentialSection";
import SOAPDraftSection from "./SOAPDraftSection";
import PendingOrdersSection from "./PendingOrdersSection";
import ImageUploadSection from "./ImageUploadSection";
import LabUploadSection from "./LabUploadSection";
import LabResultsSection from "./LabResultsSection";
import UpdateStatusBar from "./UpdateStatusBar";
import type { LabReport } from "../../types";

interface AgentSidebarProps {
  session: Session | null;
  loading?: boolean;
  onLabReport?: (report: LabReport) => void;
}

type SectionKey =
  | "alerts"
  | "medications"
  | "differential"
  | "soap"
  | "orders"
  | "images"
  | "labs"
  | "labResults";

const defaultSOAP = {
  subjective: "",
  objective: "",
  assessment: "",
  plan: "",
  status: "draft" as const,
  last_updated: "",
};

export const AgentSidebar: React.FC<AgentSidebarProps> = ({
  session,
  loading = false,
  onLabReport,
}) => {
  const [collapsed, setCollapsed] = useState<Record<SectionKey, boolean>>({
    alerts: false,
    medications: false,
    differential: false,
    soap: false,
    orders: false,
    images: false,
    labs: false,
    labResults: false,
  });

  const toggle = (key: SectionKey) =>
    setCollapsed((prev) => ({ ...prev, [key]: !prev[key] }));

  if (loading && !session) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-clinical-500 border-t-transparent" />
          <p className="text-xs text-slate-400 dark:text-slate-500">Loading session data...</p>
        </div>
      </div>
    );
  }

  const alerts = session?.clinical_alerts ?? [];
  const medications = session?.medications ?? [];
  const interactionFlags = session?.interaction_flags ?? [];
  const differential = session?.differential ?? [];
  const soapNote = session?.soap_note ?? defaultSOAP;
  const pendingOrders = session?.pending_orders ?? [];
  const imageAnalyses = session?.image_analyses ?? [];
  const labReports = session?.lab_reports ?? [];
  const sessionId = session?.id ?? "";

  return (
    <div className="space-y-4 p-4">
      {sessionId && (
        <UpdateStatusBar
          sessionId={sessionId}
          onUpdated={() => {
            /* polling handles it */
          }}
        />
      )}
      <AlertsSection
        alerts={alerts}
        collapsed={collapsed.alerts}
        onToggle={() => toggle("alerts")}
      />
      <MedicationSection
        medications={medications}
        interactionFlags={interactionFlags}
        collapsed={collapsed.medications}
        onToggle={() => toggle("medications")}
      />
      <DifferentialSection
        differential={differential}
        collapsed={collapsed.differential}
        onToggle={() => toggle("differential")}
      />
      <SOAPDraftSection
        soapNote={soapNote}
        collapsed={collapsed.soap}
        onToggle={() => toggle("soap")}
      />
      <PendingOrdersSection
        orders={pendingOrders}
        collapsed={collapsed.orders}
        onToggle={() => toggle("orders")}
      />
      {sessionId && (
        <ImageUploadSection
          sessionId={sessionId}
          imageAnalyses={imageAnalyses}
          collapsed={collapsed.images}
          onToggle={() => toggle("images")}
        />
      )}
      {sessionId && (
        <LabUploadSection
          sessionId={sessionId}
          labReports={labReports}
          onLabReport={onLabReport ?? (() => {})}
          collapsed={collapsed.labs}
          onToggle={() => toggle("labs")}
        />
      )}
      <LabResultsSection
        labReports={labReports}
        collapsed={collapsed.labResults}
        onToggle={() => toggle("labResults")}
      />
    </div>
  );
};

export default AgentSidebar;
