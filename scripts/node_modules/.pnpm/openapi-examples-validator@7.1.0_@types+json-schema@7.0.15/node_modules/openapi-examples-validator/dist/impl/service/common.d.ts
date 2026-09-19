export type JsonPathMatchData = {
    path: string;
    value: Object;
    parent: Object;
    parentProperty: string;
    hasArrExpr: boolean;
};
/**
 * Callback that is applied to a JSONPath-match.
 */
export type JsonPathMatchCallback = (value: Object, resultType: string, data: JsonPathMatchData) => any;
/**
 * Function to build a callback that is applied to a JSONPath-match.
 */
export type JsonPathMatchCallbackBuilder = (jsPath: string) => JsonPathMatchCallback;
/**
 * @typedef {{
 *     path: String,
 *     value: Object,
 *     parent: Object,
 *     parentProperty: String,
 *     hasArrExpr: Boolean
 * }} JsonPathMatchData
 */
/**
 * Callback that is applied to a JSONPath-match.
 * @callback JsonPathMatchCallback
 * @param {Object}              value       Value of the matched property
 * @param {String}              resultType  Result-type of the query
 * @param {JsonPathMatchData}   data        Object that contains additional data to the match
 */
/**
 * Function to build a callback that is applied to a JSONPath-match.
 * @callback JsonPathMatchCallbackBuilder
 * @param {string}                 jsPath  Path to the property that matched
 * @return {JsonPathMatchCallback}         Callback that is applied to a JSONPath-match
 */
/**
 * Apply the input rule to all models of type object in the input openApiSpec
 * @param {Object}                 openApiSpec           The to-be-modified schema
 * @param {Array.<String>}         examplePaths          The paths to the examples, which's content must not be modified
 * @param {JsonPathMatchCallbackBuilder}  matchCallbackBuilder    Function to build a callback
 *                                                                that will be called on each match
 */
export function applyCallbackToAllObjectModels(openApiSpec: Object, examplePaths: Array<string>, matchCallbackBuilder: JsonPathMatchCallbackBuilder): void;
