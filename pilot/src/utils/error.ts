export class HTMLResponseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'HTMLResponseError';
  }
}

export class NonJSONResponseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'NonJSONResponseError';
  }
}

export class NotFound404Error extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'NotFound404Error';
  }
}
