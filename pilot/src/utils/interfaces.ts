export interface DescriptionResponse {
      ServerTransactionID: number;
      ClientTransactionID: number;
      ErrorNumber: number;
      ErrorMessage: string;
      Value: {
        ServerName: string;
        Manufacturer: string;
        Version: string;
        Location: string;
      };
    }

export interface DeviceResponse {
  DeviceName: string;
  DeviceType: string;
  DeviceNumber: number;
  UniqueID: string;
}

export interface ConfiguredDevicesResponse {
  ServerTransactionID: number;
  ClientTransactionID: number;
  ErrorNumber: number;
  ErrorMessage: string;
  Value: DeviceResponse[];
}

export interface SupportedActionsResponse {
  ServerTransactionID: number;
  ClientTransactionID: number;
  ErrorNumber: number;
  ErrorMessage: string;
  Value: string[];
}

export interface ActionResponse {
  ServerTransactionID: number;
  ClientTransactionID: number;
  ErrorNumber: number;
  ErrorMessage: string;
  Value: string;
}
