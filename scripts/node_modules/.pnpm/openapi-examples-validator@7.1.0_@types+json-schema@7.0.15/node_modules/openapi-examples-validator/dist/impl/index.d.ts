export type Implementation = {
    buildValidationMap: (pathsExamples: Array<string>) => Record<string, Set<string>>;
    getJsonPathsToExamples: () => Array<string>;
    prepare: (openapiSpec: Object, options?: {
        noAdditionalProperties?: boolean;
        allPropertiesRequired?: boolean;
    }) => object;
};
/**
 * Get the version-specific implementation for the OpenAPI-spec. Currently v2 and v3 are supported
 * @param {Object}  openapiSpec OpenAPI-spec
 * @returns {Implementation | null}
 */
export function getImplementation(openapiSpec: Object): Implementation | null;
