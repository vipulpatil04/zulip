/**
 * Creates a unified response for the validation-result
 * @param {Object}                      options
 * @param {Array.<ApplicationError>}    options.errors
 * @param {ValidationStatistics}        [options.statistics]
 * @returns {ValidationResponse}
 * @private
 */
export function createValidationResponse({ errors, statistics }: {
    errors: Array<ApplicationError>;
    statistics?: ValidationStatistics | undefined;
}): ValidationResponse;
/**
 * Includes all referenced, external schemas (by the keyword `$ref`) into the schema
 *
 * CAUTION: This function is not concurrency-safe !!
 * This function changes the working dir and sets it back. This may become an concurrency issue when there are
 * other tasks running that rely on the working dir while this function waits for the asynchronous task of
 * dereferencing to complete.
 *
 * @param {String} pathToSchema     File-path to the schema
 * @param {Object} jsonSchema       Schema with potential externally referenced schemas
 * @returns {Promise<Object>}       Dereferenced schema
 */
export function dereferenceJsonSchema(pathToSchema: string, jsonSchema: Object): Promise<Object>;
import type { ApplicationError } from "../application-error";
import type { ValidationStatistics } from "..";
import type { ValidationResponse } from "..";
