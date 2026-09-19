import * as Koa from 'koa';
import { BodyParserOptions } from './body-parser.types.js';
import 'co-body';

declare module 'koa' {
    interface Request {
        body?: unknown;
        rawBody: string;
    }
}
declare module 'http' {
    interface IncomingMessage {
        body?: unknown;
        rawBody: string;
    }
}
declare function bodyParserWrapper(opts?: BodyParserOptions): (ctx: Koa.Context, next: Koa.Next) => Promise<any>;

export { bodyParserWrapper };
