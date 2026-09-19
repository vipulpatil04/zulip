/**
 * Builds a map with the json-pointers to the response-schema as key and the json-pointers to the examples, as value.
 * The pointer of the schema is derived from the pointer to the example and doesn't necessarily mean
 * that the schema actually exists.
 * @param {Array.<String>}  pathsExamples   Paths to the examples
 * @returns {Record<String, Set<String>>} Map with schema-pointers as key and example-pointers as value
 * @private
 */
export function buildValidationMap(pathsExamples: Array<string>): Record<string, Set<string>>;
/**
 * Get the JSONPaths to the examples
 * @returns {Array.<String>}    JSONPaths to the examples
 */
export function getJsonPathsToExamples(): Array<string>;
/**
 * Pre-processes the OpenAPI-spec, for further use.
 * The passed spec won't be modified. If a modification happens, a modified copy will be returned.
 * @param {Object}  openapiSpec                     The OpenAPI-spec as JSON-schema
 * @param {Object}  [options]
 * @param {boolean} [options.noAdditionalProperties=false] Don't allow properties that are not defined in the schema
 * @param {boolean} [options.allPropertiesRequired=false] Make all properties required
 * @return {Object} The prepared OpenAPI-spec
 */
export function prepare(openapiSpec: Object, { noAdditionalProperties, allPropertiesRequired }?: {
    noAdditionalProperties?: boolean | undefined;
    allPropertiesRequired?: boolean | undefined;
}): Object;
