export interface AlpacaDescription {
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

export interface AlpacaDevice {
  DeviceName: string;
  DeviceType: string;
  DeviceNumber: number;
  UniqueID: string;
}

export interface AlpacaConfiguredDevices {
  ServerTransactionID: number;
  ClientTransactionID: number;
  ErrorNumber: number;
  ErrorMessage: string;
  Value: AlpacaDevice[];
}


