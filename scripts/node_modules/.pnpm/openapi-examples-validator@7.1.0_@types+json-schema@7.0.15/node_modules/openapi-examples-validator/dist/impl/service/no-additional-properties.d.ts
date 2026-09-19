/**
 * Sets the flag to indicate that it doesn't allow properties that are not described in the schema
 * @param {Object}                  openApiSpec         The to-be-modified schema
 * @param {Array.<String>}          [examplePaths=[]]   The paths to the examples, which's content must not be modified
 */
export function setNoAdditionalProperties(openApiSpec: Object, examplePaths?: Array<string>): void;
