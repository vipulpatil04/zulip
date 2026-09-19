/**
 * Sets all properties of each object to required
 * @param {Object}                  openApiSpec         The to-be-modified schema
 * @param {Array.<String>}          [examplePaths=[]]   The paths to the examples, which's content must not be modified
 */
export function setAllPropertiesRequired(openApiSpec: Object, examplePaths?: Array<string>): void;
