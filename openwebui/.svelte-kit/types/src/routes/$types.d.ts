import type * as Kit from '@sveltejs/kit';

type Expand<T> = T extends infer O ? { [K in keyof O]: O[K] } : never;
// @ts-ignore
type MatcherParam<M> = M extends (param : string) => param is infer U ? U extends string ? U : string : string;
type RouteParams = {  };
type RouteId = '/';
type MaybeWithVoid<T> = {} extends T ? T | void : T;
export type RequiredKeys<T> = { [K in keyof T]-?: {} extends { [P in K]: T[K] } ? never : K; }[keyof T];
type OutputDataShape<T> = MaybeWithVoid<Omit<App.PageData, RequiredKeys<T>> & Partial<Pick<App.PageData, keyof T & keyof App.PageData>> & Record<string, any>>
type EnsureDefined<T> = T extends null | undefined ? {} : T;
type OptionalUnion<U extends Record<string, any>, A extends keyof U = U extends U ? keyof U : never> = U extends unknown ? { [P in Exclude<A, keyof U>]?: never } & U : never;
export type Snapshot<T = any> = Kit.Snapshot<T>;
type LayoutRouteId = RouteId | "/(app)" | "/(app)/admin" | "/(app)/admin/analytics" | "/(app)/admin/analytics/[tab]" | "/(app)/admin/evaluations" | "/(app)/admin/evaluations/[tab]" | "/(app)/admin/functions" | "/(app)/admin/functions/create" | "/(app)/admin/functions/edit" | "/(app)/admin/settings" | "/(app)/admin/settings/[tab]" | "/(app)/admin/users" | "/(app)/admin/users/[tab]" | "/(app)/c/[id]" | "/(app)/channels/[id]" | "/(app)/home" | "/(app)/notes" | "/(app)/notes/[id]" | "/(app)/notes/new" | "/(app)/playground" | "/(app)/playground/completions" | "/(app)/workspace" | "/(app)/workspace/functions/create" | "/(app)/workspace/knowledge" | "/(app)/workspace/knowledge/[id]" | "/(app)/workspace/knowledge/create" | "/(app)/workspace/models" | "/(app)/workspace/models/create" | "/(app)/workspace/models/edit" | "/(app)/workspace/prompts" | "/(app)/workspace/prompts/create" | "/(app)/workspace/prompts/edit" | "/(app)/workspace/tools" | "/(app)/workspace/tools/create" | "/(app)/workspace/tools/edit" | "/auth" | "/error" | "/s/[id]" | "/watch" | null
type LayoutParams = RouteParams & { tab?: string; id?: string }
type LayoutParentData = EnsureDefined<{}>;

export type LayoutServerData = null;
export type LayoutLoad<OutputData extends OutputDataShape<LayoutParentData> = OutputDataShape<LayoutParentData>> = Kit.Load<LayoutParams, LayoutServerData, LayoutParentData, OutputData, LayoutRouteId>;
export type LayoutLoadEvent = Parameters<LayoutLoad>[0];
export type LayoutData = Expand<Omit<LayoutParentData, keyof LayoutParentData & EnsureDefined<LayoutServerData>> & OptionalUnion<EnsureDefined<LayoutParentData & EnsureDefined<LayoutServerData>>>>;
export type LayoutProps = { data: LayoutData; children: import("svelte").Snippet }