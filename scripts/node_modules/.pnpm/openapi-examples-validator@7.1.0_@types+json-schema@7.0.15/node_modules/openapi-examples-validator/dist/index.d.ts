export default validateExamples;
/**
 * ValidationStatistics
 */
export type ValidationStatistics = {
    [SYM__INTERNAL]: {
        [PROP__SCHEMAS_WITH_EXAMPLES]: Set<Object>;
    };
    schemasWithExamples: number;
    examplesTotal: number;
    examplesWithoutSchema: number;
    matchingFilePathsMapping?: number;
};
/**
 * ValidationResponse
 */
export type ValidationResponse = {
    valid: boolean;
    statistics: ValidationStatistics;
    errors: Array<ApplicationError>;
};
export type ValidationHandler = (statistics: ValidationStatistics) => Array<ApplicationError>;
/**
 * ErrorJsonPathNotFound
 */
export type ErrorJsonPathNotFound = {
    cause: {
        params?: {
            path?: string;
        };
    };
};
/**
 * ValidationStatistics
 * @typedef {{
 *      [SYM__INTERNAL]: {
 *          [PROP__SCHEMAS_WITH_EXAMPLES]: Set<Object>
 *      },
 *      schemasWithExamples: number,
 *      examplesTotal: number,
 *      examplesWithoutSchema: number,
 *      matchingFilePathsMapping?: number
 * }} ValidationStatistics
 */
/**
 * ValidationResponse
 * @typedef {{
 *      valid: boolean,
 *      statistics: ValidationStatistics,
 *      errors: Array.<ApplicationError>
 * }} ValidationResponse
 */
/**
 * @callback ValidationHandler
 * @param {ValidationStatistics}    statistics
 * @returns {Array.<ApplicationError>}
 */
/**
 * Validates OpenAPI-spec with embedded examples.
 * @param {Object}  openapiSpec OpenAPI-spec
 * @param {Object} [options]
 * @param {boolean} [options.noAdditionalProperties=false] Don't allow properties that are not defined in the schema
 * @param {boolean} [options.allPropertiesRequired=false] Make all properties required
 * @param {Array.<string>} [options.ignoreFormats]  List of datatype formats that shall be ignored (to prevent
 *                                                  "unsupported format" errors). If an Array with only one string is
 *                                                  provided where the formats are separated with `\n`, the entries
 *                                                  will be expanded to a new array containing all entries.
 * @returns {Promise<ValidationResponse>}
 */
export function validateExamples(openapiSpec: Object, { noAdditionalProperties, ignoreFormats, allPropertiesRequired }?: {
    noAdditionalProperties?: boolean | undefined;
    allPropertiesRequired?: boolean | undefined;
    ignoreFormats?: string[] | undefined;
}): Promise<ValidationResponse>;
/**
 * Validates OpenAPI-spec with embedded examples.
 * @param {string}  filePath                        File-path to the OpenAPI-spec
 * @param {Object}  [options]
 * @param {boolean} [options.noAdditionalProperties=false] Don't allow properties that are not defined in the schema
 * @param {boolean} [options.allPropertiesRequired=false] Make all properties required
 * @param {Array.<string>} [options.ignoreFormats]  List of datatype formats that shall be ignored (to prevent
 *                                                  "unsupported format" errors). If an Array with only one string is
 *                                                  provided where the formats are separated with `\n`, the entries
 *                                                  will be expanded to a new array containing all entries.
 * @returns {Promise<ValidationResponse>}
 */
export function validateFile(filePath: string, { noAdditionalProperties, ignoreFormats, allPropertiesRequired }?: {
    noAdditionalProperties?: boolean | undefined;
    allPropertiesRequired?: boolean | undefined;
    ignoreFormats?: string[] | undefined;
}): Promise<ValidationResponse>;
/**
 * Validates a single external example.
 * @param {String}  filePathSchema                  File-path to the OpenAPI-spec
 * @param {String}  pathSchema                      JSON-path to the schema
 * @param {String}  filePathExample                 File-path to the external example-file
 * @param {Object}  [options]
 * @param {boolean} [options.noAdditionalProperties=false] Don't allow properties that are not described in the schema
 * @param {boolean} [options.allPropertiesRequired=false] Make all properties required
 * @param {Array.<string>} [options.ignoreFormats]  List of datatype formats that shall be ignored (to prevent
 *                                                  "unsupported format" errors). If an Array with only one string is
 *                                                  provided where the formats are separated with `\n`, the entries
 *                                                  will be expanded to a new array containing all entries.
 * @returns {Promise<ValidationResponse>}
 */
export function validateExample(filePathSchema: string, pathSchema: string, filePathExample: string, { noAdditionalProperties, ignoreFormats, allPropertiesRequired }?: {
    noAdditionalProperties?: boolean | undefined;
    allPropertiesRequired?: boolean | undefined;
    ignoreFormats?: string[] | undefined;
}): Promise<ValidationResponse>;
/**
 * Validates examples by mapping-files.
 * @param {string}  filePathSchema              File-path to the OpenAPI-spec
 * @param {string}  globMapExternalExamples     File-path (globs are supported) to the mapping-file containing JSON-
 *                                              paths to schemas as key and a single file-path or Array of file-paths
 *                                              to external examples
 * @param {Object}  [options]
 * @param {boolean} [options.cwdToMappingFile=false]
 *                                              Change working directory for resolving the example-paths (relative to
 *                                              the mapping-file)
 * @param {boolean} [options.noAdditionalProperties=false] Don't allow properties that are not defined in the schema
 * @param {boolean} [options.allPropertiesRequired=false] Make all properties required
 * @param {Array.<string>} [options.ignoreFormats] List of datatype formats that shall be ignored (to prevent
 *                                              "unsupported format" errors). If an Array with only one string is
 *                                              provided where the formats are separated with `\n`, the entries
 *                                              will be expanded to a new array containing all entries.
 * @returns {Promise<ValidationResponse>}
 */
export function validateExamplesByMap(filePathSchema: string, globMapExternalExamples: string, { cwdToMappingFile, noAdditionalProperties, ignoreFormats, allPropertiesRequired }?: {
    cwdToMappingFile?: boolean | undefined;
    noAdditionalProperties?: boolean | undefined;
    allPropertiesRequired?: boolean | undefined;
    ignoreFormats?: string[] | undefined;
}): Promise<ValidationResponse>;
declare const SYM__INTERNAL: unique symbol;
declare const PROP__SCHEMAS_WITH_EXAMPLES: "schemasWithExamples";
import { ApplicationError } from "./application-error";
