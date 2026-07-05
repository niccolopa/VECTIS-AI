// Connector-status client — GET /api/v1/connectors.
import { http } from "@/services/apiClient";
import type { ConnectorStatusResponse } from "@/types/connectors";

export function fetchConnectorStatus(): Promise<ConnectorStatusResponse> {
  return http<ConnectorStatusResponse>("/api/v1/connectors");
}
