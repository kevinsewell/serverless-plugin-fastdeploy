Serverless Fast Deploy Plugin 
==========================
[![serverless](http://public.serverless.com/badges/v3.svg)](http://www.serverless.com)
[![npm version](https://badge.fury.io/js/serverless-plugin-fastdeploy.svg)](https://badge.fury.io/js/serverless-plugin-fastdeploy)
[![npm downloads](https://img.shields.io/npm/dm/serverless-plugin-fastdeploy.svg)](https://www.npmjs.com/package/serverless-plugin-fastdeploy)
[![license](https://img.shields.io/npm/l/serverless-plugin-fastdeploy.svg)](https://raw.githubusercontent.com/aronim/serverless-plugin-fastdeploy/master/LICENSE)

Lightening Fast Serverless Deployments

**Requirements:**
* Serverless *v1.12.x* or higher.
* AWS provider

### How it works

I found that while working with Python libraries such Numpy and Pandas, my deploys became very slow and expensive (I 
work off a mobile data plan) due to the increased package size. This plugin deploys a specialized Lambda always you to 
only deploy the files that are most likely to change. It does this by merging the incoming files with the latest 
existing package on S3. So now when I deploy a change, I am sending a few KB across the wire each time, not 60 MB.

### Caveats

#### A note about merging the update package with the base package

y first attempt was to just use the latest existing deployment package on S3, unpack that and
create a new package with the update files. This was a bit "slow", so now I create a base package which is the full 
previous deployment package without the files described by the `custom.fastDelpoy.include` property. This means that I 
can simply append the new files, resulting in an even faster deploy. The unfortunately side effect being that if you 
change the `custom.fastDelpoy.include` property, you need to do a full deployment before doing your next FastDeploy.

#### Custom deployment bucket

At the moment this plugin bypasses all of the standard deployment lifecycle stages, so I am not yet able to get hold of 
the auto generated deployment bucket. As such this plugin only works if you have created a custom deployment bucket and 
configured it via the `provider.deploymentBucket` property.

#### IAM Role

The FastDeploy Lambda requires the following permissions on the deployment bucket. Either this can be added to the 
services default role, or you can create a new role and configure it via the `custom.fastDelpoy.role` property.

```yaml
- Effect: Allow
  Action:
    - s3:GetObject
    - s3:PutObject
  Resource: arn:aws:s3:::aronim-serverless/*
- Effect: Allow
  Action:
    - s3:ListBucket
  Resource: arn:aws:s3:::aronim-serverless     
```

### Setup

 Install via npm in the root of your Serverless service:
```
npm install serverless-plugin-fastdeploy --save-dev
```

* Add the plugin to the `plugins` array in your Serverless `serverless.yml`:

```yml
plugins:
  - serverless-plugin-fastdeploy
```

### Run

```bash
sls fastdeploy
```

### Configuration

The `custom.fastDelpoy.include` property describes which files to include in the update package, and exclude from the 
base package. This can be an array if you are just working in single module project, or an object if you are working with a 
multi-module project.

```yml
service: ServerlessFastDeployExample

plugins:
  - serverless-plugin-fastdeploy

provider:
  ...
  role: DefaultRole
  deploymentBucket: aronim-serverless

custom:
  fastDeploy:
    include:
      - package_one/**
      - package_two/**

######      
# OR #      
###### 
 
custom:
  fastDeploy:
    include:
      ".": service_one/**
      "../../modules/module-two": module_two/**     

resources:
  Resources:
    DefaultRole:
      Type: AWS::IAM::Role
      Properties:
        Path: /
        RoleName: ${self:service}-${self:provider.stage}
        AssumeRolePolicyDocument:
          Version: "2012-10-17"
          Statement:
            - Effect: Allow
              Principal:
                Service:
                  - lambda.amazonaws.com
              Action: sts:AssumeRole
        Policies:
          - PolicyName: ${self:service}-${self:provider.stage}
            PolicyDocument:
              Version: "2012-10-17"
              Statement:
                - Effect: Allow
                  Action:
                    - logs:CreateLogGroup
                    - logs:CreateLogStream
                    - logs:PutLogEvents
                  Resource: arn:aws:logs:${self:provider.region}:*:log-group:/aws/lambda/*:*:*
                - Effect: Allow
                  Action:
                    - s3:GetObject
                    - s3:PutObject
                  Resource: arn:aws:s3:::aronim-serverless/*
                - Effect: Allow
                  Action:
                    - s3:ListBucket
                  Resource: arn:aws:s3:::aronim-serverless     
```

## Cost
Since we are deploying an additional Lambda, there are some neglible cost implications. The default memory allocated to 
the FastDeploy Lambda is 512MB, but this can be increased or decreased using the `custom.fastDelpoy.memory` property.

## Acknowledgements
A big thank you to [FidelLimited](https://github.com/FidelLimited/), I blatently plagiarized their WarmUp plugin for the 
basis of the FastDeploy Lambda :-) As they say "Mimicry highest form of flattery".


## Contribute

Help us making this plugin better and future proof.

* Clone the code
* Install the dependencies with `npm install`
* Create a feature branch `git checkout -b new_feature`
* Lint with standard `npm run lint`

## License

This software is released under the MIT license. See [the license file](LICENSE) for more details.
