export const WORLD_LOCATIONS = ["usa", "world"];
export const COUNT_METHODS = ["dodd", "net"];
export const SCOPES = (() => {
    const scopes = [];
    COUNT_METHODS.forEach((count) => {
        WORLD_LOCATIONS.forEach((location) => {
            scopes.push({ location, count });
        });
    });
    return scopes;
})();
