"use strict";

const archiver = require("archiver");
const BbPromise = require("bluebird");
const fs = require("fs-extra");
const path = require("path");

/**
 * @classdesc   Perform Lightning Fast Deployments
 * @class       ServerlessPluginFastDeploy
 */
class ServerlessPluginFastDeploy {

    /**
     * @constructor
     *
     * @param serverless
     * @param options
     */
    constructor(serverless, options) {
        this.serverless = serverless;
        this.options = options;
        this.provider = serverless.getProvider("aws");
        this.custom = this.serverless.service.custom;

        this.commands = {
            fastdeploy: {
                usage: "Perform Lightning Fast Deployment",
                lifecycleEvents: ["fastdeploy"]
            }
        };

        this.hooks = {
            "fastdeploy:fastdeploy": this.performFastDeploy.bind(this),
            "after:package:initialize": this.afterPackageInitialize.bind(this),
            "after:package:createDeploymentArtifacts": this.afterCreateDeploymentArtifacts.bind(this),
            "after:deploy:deploy": this.afterDeployFunctions.bind(this)
        };
    }

    performFastDeploy() {

        this.configPlugin();

        return this.createFastDeployUpdateArtifact()
            .then(this.invokeFastDeployFunction.bind(this))
            .then(this.updateFunctionsCode.bind(this));
    }

    /**
     * @description After package initialize hook. Create FastDeploy function and add it to the service.
     *
     * @fulfil {} — Warm up set
     * @reject {Error} Warm up error
     *
     * @return {(boolean|Promise)}
     * */
    afterPackageInitialize() {
        // See https://github.com/serverless/serverless/issues/2631
        this.options.stage = this.options.stage
            || this.serverless.service.provider.stage
            || (this.serverless.service.defaults && this.serverless.service.defaults.stage)
            || "dev";
        this.options.region = this.options.region
            || this.serverless.service.provider.region
            || (this.serverless.service.defaults && this.serverless.service.defaults.region)
            || "us-east-1";

        return this.createFastDeployFunctionArtifact()
            .then(() => this.addFastDeployFunctionToService());
    }

    /**
     * @description After create deployment artifacts. Clean prefix folder.
     *
     * @fulfil {} — Optimization finished
     * @reject {Error} Optimization error
     *
     * @return {Promise}
     * */
    afterCreateDeploymentArtifacts() {
        return this.cleanFolder()
    }

    /**
     * @description After deploy functions hooks
     *
     * @fulfil {} — Functions warmed up sucessfuly
     * @reject {Error} Functions couldn"t be warmed up
     *
     * @return {Promise}
     * */
    afterDeployFunctions() {
        this.configPlugin();
    }

    configPlugin() {
        /** Set warm up folder, file and handler paths */
        this.folderName = "_fastdeploy";
        if (this.custom && this.custom.fastDeploy && typeof this.custom.fastDeploy.folderName === "string") {
            this.folderName = this.custom.fastDeploy.folderName
        }
        this.pathFolder = path.join(this.serverless.config.servicePath, this.folderName);
        this.pathFile = path.join(this.pathFolder, "fast_deploy.py");
        this.pathHandler = `${this.folderName}/fast_deploy.handle`;

        this.artifactFilePath = path.join(this.serverless.config.servicePath,
            ".serverless",
            `${this.serverless.service.service}-FastDeployUpdate.zip`
        );

        /** Default options */
        this.fastDeploy = {
            cleanFolder: true,
            memorySize: 512,
            name: this.serverless.service.service + "-" + this.options.stage + "-FastDeploy",
            timeout: 30,
            includePatterns: []
        };

        /** Set global custom options */
        if (!this.custom || !this.custom.fastDeploy) {
            return
        }

        /** Clean folder */
        if (typeof this.custom.fastDeploy.cleanFolder === "boolean") {
            this.fastDeploy.cleanFolder = this.custom.fastDeploy.cleanFolder
        }

        /** Memory size */
        if (typeof this.custom.fastDeploy.memorySize === "number") {
            this.fastDeploy.memorySize = this.custom.fastDeploy.memorySize
        }

        /** Function name */
        if (typeof this.custom.fastDeploy.name === "string") {
            this.fastDeploy.name = this.custom.fastDeploy.name
        }

        /** Role */
        if (typeof this.custom.fastDeploy.role === "string") {
            this.fastDeploy.role = this.custom.fastDeploy.role
        }

        /** Tags */
        if (typeof this.custom.fastDeploy.tags === "object") {
            this.fastDeploy.tags = this.custom.fastDeploy.tags
        }

        /** Timeout */
        if (typeof this.custom.fastDeploy.timeout === "number") {
            this.fastDeploy.timeout = this.custom.fastDeploy.timeout
        }

        /** Include Pattern */
        if (typeof this.custom.fastDeploy.include === "object") {
            this.fastDeploy.include = this.custom.fastDeploy.include
        }
    }

    cleanFolder() {
        if (fs.existsSync(this.pathFolder)) {
            return fs.remove(this.pathFolder)
        }

        return BbPromise.resolve();
    }

    /**
     * Create Update Artifact
     *
     * @returns {*|{lifecycleEvents}|void}
     */
    createFastDeployUpdateArtifact() {
        const output = fs.createWriteStream(this.artifactFilePath);
        const zip = archiver.create("zip");

        zip.pipe(output);

        const globalGlobOptions = {
            cwd: this.serverless.config.servicePath,
            silent: true,
            follow: true,
            nodir: true
        };

        if (Array.isArray(this.fastDeploy.include)) {
            this.fastDeploy.include.forEach(pattern => zip.glob(pattern, globalGlobOptions));
        }
        else {
            Object.keys(this.fastDeploy.include)
                .forEach(relativePath => {
                    const localGlobOptions = Object.assign({}, globalGlobOptions);
                    localGlobOptions.cwd = path.join(this.serverless.config.servicePath, relativePath);
                    const pattern = this.fastDeploy.include[relativePath];
                    zip.glob(pattern, localGlobOptions)
                });
        }

        zip.finalize();

        return new Promise((resolve, reject) => {
            let errored;

            output.on("close", () => {
                if (!errored) resolve()
            });

            output.on("error", err => {
                errored = true;
                reject(err);
            })
        })
    }

    createFastDeployFunctionArtifact() {
        this.configPlugin();

        return this.cleanFolder()
            .then(() => fs.mkdirs(this.pathFolder))
            .then(() => fs.createReadStream(__dirname + "/fast_deploy.py").pipe(fs.createWriteStream(this.pathFile)));
    }


    addFastDeployFunctionToService() {
        /** Serverless FastDeploy function */
        this.serverless.service.functions.FastDeploy = {
            description: "Serverless Fast Deploy Plugin",
            events: [],
            handler: this.pathHandler,
            memorySize: this.fastDeploy.memorySize,
            name: this.fastDeploy.name,
            runtime: "python3.6",
            package: {
                individually: true,
                exclude: ["**"],
                include: [this.folderName + "/**"]
            },
            timeout: this.fastDeploy.timeout
        };

        if (this.fastDeploy.role) {
            this.serverless.service.functions.fastDeploy.role = this.fastDeploy.role
        }

        if (this.fastDeploy.tags) {
            this.serverless.service.functions.fastDeploy.tags = this.fastDeploy.tags
        }

        /** Return service function object */
        return this.serverless.service.functions.FastDeploy
    }

    /**
     * Invoke Fast Deploy Function
     * @returns {*}
     */
    invokeFastDeployFunction() {
        const base64Data = fs.readFileSync(this.artifactFilePath, "base64");

        const globPatterns = Array.isArray(this.fastDeploy.include) ?
            this.fastDeploy.include :
            Object.values(this.fastDeploy.include);

        const params = {
            FunctionName: this.fastDeploy.name,
            InvocationType: "RequestResponse",
            LogType: "None",
            Qualifier: process.env.SERVERLESS_ALIAS || "$LATEST",
            Payload: JSON.stringify({
                serviceName: this.serverless.service.service,
                deploymentStage: this.serverless.service.provider.stage,
                deploymentS3BucketName: this.serverless.service.provider.deploymentBucket,
                base64EncodedZipFileBytes: base64Data,
                globPatterns: globPatterns,
            })
        };

        return this.provider.request("Lambda", "invoke", params)
            .then(invokeFunctionResponse => {
                let payload = invokeFunctionResponse.Payload;
                let fastDeployResponse = JSON.parse(payload);

                if (invokeFunctionResponse.FunctionError) {
                    throw new Error(fastDeployResponse.errorMessage)
                }

                return fastDeployResponse.s3ObjectKey;
            })
    }

    /**
     * Invoke Fast Deploy Function
     * @returns {*}
     */
    updateFunctionsCode(s3ObjectKey) {

        let functions = this.serverless.service.functions;
        let functionNames = Object.keys(functions);
        const promises = functionNames.map(functionName => {
            const function_ = functions[functionName];

            const params = {
                FunctionName: function_.name,
                S3Bucket: this.serverless.service.provider.deploymentBucket,
                S3Key: s3ObjectKey,
            };

            return this.provider.request("Lambda", "updateFunctionCode", params)
        });

        return BbPromise.all(promises);
    }
}

/** Export ServerlessPluginFastDeploy class */
module.exports = ServerlessPluginFastDeploy;
