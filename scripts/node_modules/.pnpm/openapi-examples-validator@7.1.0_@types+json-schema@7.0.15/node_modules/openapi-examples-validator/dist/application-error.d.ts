export type CustomError = {};
/**
 * ApplicationErrorOptions
 */
export type ApplicationErrorOptions = {
    instancePath?: string;
    examplePath?: string;
    exampleFilePath?: string;
    keyword?: string;
    message?: string;
    mapFilePath?: string;
    params?: {
        path?: string;
        missingProperty?: string;
        type?: string;
    };
    schemaPath?: string;
};
/**
 * Unified application-error
 */
export class ApplicationError {
    /**
     * Factory-function, which is able to consume validation-errors and JS-errors. If a validation error is passed, all
     * properties will be adopted.
     * @param {Error|CustomError}   err     Javascript-, validation- or custom-error, to create the application-error
     *                                      from
     * @returns {ApplicationError} Unified application-error instance
     */
    static create(err: Error | CustomError): ApplicationError;
    /**
     * Constructor
     * @param {string}                  type        Type of error (see statics)
     * @param {ApplicationErrorOptions} [options]   Optional properties
     */
    constructor(type: string, options?: ApplicationErrorOptions);
}
export namespace ErrorType {
    let jsENOENT: any;
    let jsonPathNotFound: string;
    let errorAndErrorsMutuallyExclusive: string;
    let parseError: string;
    let validation: string;
}
