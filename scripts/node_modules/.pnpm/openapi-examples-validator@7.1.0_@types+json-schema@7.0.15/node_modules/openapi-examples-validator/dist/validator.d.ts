/**
 * Get a factory-function to create a prepared validator-instance
 * @param {Object}  specSchema  OpenAPI-spec of which potential local references will be extracted
 * @param {ajv.Options} [options] Options for the validator
 * @returns {function(): Ajv}
 */
export function getValidatorFactory(specSchema: Object, options?: ajv.Options): () => Ajv;
/**
 * Compiles the validator-function.
 * @param {Ajv}             validator       Validator-instance
 * @param {Object}          responseSchema  The response-schema, against the examples will be validated
 * @returns {ajv.ValidateFunction}
 */
export function compileValidate(validator: Ajv, responseSchema: Object): ajv.ValidateFunction;
import type * as ajv from 'ajv-draft-04';
import { default as Ajv } from "ajv-draft-04";
